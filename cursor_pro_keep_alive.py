import sys
import psutil
import time
import random
from logger import info, warning, error
import traceback
from config import (
    LOGIN_URL,
    SIGN_UP_URL,
    SETTINGS_URL,
    EMAIL_DOMAINS,
    REGISTRATION_MAX_RETRIES,
    EMAIL_TYPE
)


if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

from browser_utils import BrowserManager
from get_email_code import EmailVerificationHandler

from datetime import datetime  # 添加这行导入

TOTAL_USAGE = 0


def handle_turnstile(tab):
    info("=============正在检测 Turnstile 验证=============")
    max_count = 5
    try:
        count = 1
        while True:
            if count > max_count:
                error("Turnstile 验证次数超过最大限制，退出")
                return False
            info(f"正在进行 Turnstile 第 {count} 次验证中...")
            try:
                # 检查页面状态，但不直接返回，先检查是否有Turnstile验证需要处理
                page_ready = False
                if tab.ele("@name=password"):
                    info("检测到密码输入页面，检查是否有验证需要处理...")
                    page_ready = True
                elif tab.ele("@data-index=0"):
                    info("检测到验证码输入页面，检查是否有验证需要处理...")
                    page_ready = True
                elif tab.ele("Account Settings"):
                    info("检测到账户设置页面，检查是否有验证需要处理...")
                    page_ready = True

                # 即使页面已经准备好，也检查是否有Turnstile验证需要处理
                info("检测 Turnstile 验证...")
                try:
                    challengeCheck = (
                        tab.ele("@id=cf-turnstile", timeout=2)
                        .child()
                        .shadow_root.ele("tag:iframe")
                        .ele("tag:body")
                        .sr("tag:input")
                    )

                    if challengeCheck:
                        info("检测到 Turnstile 验证，正在处理...")
                        challengeCheck.click()
                        time.sleep(2)
                        info("Turnstile 验证通过")
                        return True
                    else:
                        info("未检测到 Turnstile 验证")
                except:
                    pass
                # 如果页面已准备好且没有验证需要处理，则可以返回
                if page_ready:
                    info("页面已准备好，没有检测到需要处理的验证")
                    break
            except:
                pass
            time.sleep(random.uniform(1, 2))
            count += 1
        return True  # 返回True表示页面已准备好
    except Exception as e:
        info(f"Turnstile 验证失败: {str(e)}")
        return False


def get_cursor_session_token(tab, max_attempts=5, retry_interval=3):
    try:
        tab.get(SETTINGS_URL)
        time.sleep(5)
        try:
            usage_selector = (
                "css:div.col-span-2 > div > div > div > div > "
                "div:nth-child(1) > div.flex.items-center.justify-between.gap-2 > "
                "span.font-mono.text-sm\\/\\[0\\.875rem\\]"
            )
            usage_ele = tab.ele(usage_selector)
            total_usage = "unknown"
            if usage_ele:
                total_usage = usage_ele.text.split("/")[-1].strip()
                global TOTAL_USAGE
                TOTAL_USAGE = total_usage
                info(f"使用限制: {total_usage}")
            else:
                warning("未能找到使用量元素")
        except Exception as e:
            warning(f"获取使用量信息失败: {str(e)}")
            # 继续执行，不要因为获取使用量失败而中断整个流程

        info("获取Cookie中...")
        attempts = 0

        while attempts < max_attempts:
            try:
                cookies = tab.cookies()
                for cookie in cookies:
                    if cookie.get("name") == "WorkosCursorSessionToken":
                        user = cookie["value"].split("%3A%3A")[0]
                        token = cookie["value"].split("%3A%3A")[1]
                        info(f"获取到账号Token: {token}, 用户: {user}")
                        return token, user

                attempts += 1
                if attempts < max_attempts:
                    warning(
                        f"未找到Cursor会话Token，重试中... ({attempts}/{max_attempts})"
                    )
                    time.sleep(retry_interval)
                else:
                    info("未找到Cursor会话Token，已达到最大尝试次数")

            except Exception as e:
                info(f"获取Token出错: {str(e)}")
                attempts += 1
                if attempts < max_attempts:
                    info(
                        f"重试获取Token，等待时间: {retry_interval}秒，尝试次数: {attempts}/{max_attempts}"
                    )
                    time.sleep(retry_interval)

        return False

    except Exception as e:
        warning(f"获取Token过程出错: {str(e)}")
        return False


def sign_up_account(browser, tab, account_info):
    info("=============开始注册账号=============")
    info(
        f"账号信息: 邮箱: {account_info['email']}, 密码: {account_info['password']}, 姓名: {account_info['first_name']} {account_info['last_name']}"
    )
    if EMAIL_TYPE == "zmail":
        EmailVerificationHandler.create_zmail_email(account_info)
    tab.get(SIGN_UP_URL)

    tab.wait(2)

    if tab.ele("@name=cf-turnstile-response"):
        error("开屏就是检测啊，大佬你的IP或UA需要换一下了啊，有问题了...要等一下")

    try:
        if tab.ele("@name=first_name"):
            info("=============正在填写个人信息=============")
            tab.actions.click("@name=first_name").input(account_info["first_name"])
            info(f"已输入名字: {account_info['first_name']}")
            time.sleep(random.uniform(1, 3))

            tab.actions.click("@name=last_name").input(account_info["last_name"])
            info(f"已输入姓氏: {account_info['last_name']}")
            time.sleep(random.uniform(1, 3))

            tab.actions.click("@name=email").input(account_info["email"])
            info(f"已输入邮箱: {account_info['email']}")
            time.sleep(random.uniform(1, 3))

            info("=============提交个人信息=============")
            tab.actions.click("@type=submit")
            time.sleep(random.uniform(0.2, 1))
            if (
                    tab.ele("verify the user is human. Please try again.")
                    or tab.ele("Can't verify the user is human. Please try again.")
                    or tab.ele("Can‘t verify the user is human. Please try again.")
            ):
                info("检测到turnstile验证失败，（IP问题、UA问题、域名问题）...正在重试...")
                return "EMAIL_USED"
    except Exception as e:
        info(f"填写个人信息失败: {str(e)}")
        return "ERROR"

    handle_turnstile(tab)

    if tab.ele("verify the user is human. Please try again.") or tab.ele(
        "Can't verify the user is human. Please try again."
    ):
        info("检测到turnstile验证失败，正在重试...")
        return "EMAIL_USED"

    try:
        if tab.ele("@name=password"):
            info(f"设置密码：{account_info['password']}")
            tab.ele("@name=password").input(account_info["password"])
            time.sleep(random.uniform(1, 2))

            info("提交密码...")
            tab.ele("@type=submit").click()
            info("密码设置成功,等待系统响应....")

    except Exception as e:
        info(f"密码设置失败: {str(e)}")
        return "ERROR"

    info("处理最终验证...")
    handle_turnstile(tab)

    if tab.ele("This email is not available."):
        info("邮箱已被使用")
        return "EMAIL_USED"

    if tab.ele("Sign up is restricted."):
        info("注册限制")
        return "SIGNUP_RESTRICTED"

    # 创建邮件处理器
    email_handler = EmailVerificationHandler()
    i = 0
    while i < 5:
        try:
            time.sleep(random.uniform(0.2, 1))
            if tab.ele("Account Settings"):
                info("注册成功，已进入账号设置页面")
                break
            if tab.ele("@data-index=0"):
                info("等待输入验证码...")
                # 切换到邮箱标签页
                code = email_handler.get_verification_code(
                    source_email=account_info["email"]
                )
                if code is None:
                    info("未获取到验证码...系统异常，正在退出....")
                    return "EMAIL_GET_CODE_FAILED"
                info(f"输入验证码: {code}")
                i = 0
                for digit in code:
                    tab.ele(f"@data-index={i}").input(digit)
                    time.sleep(random.uniform(0.3, 0.6))
                    i += 1
                info("验证码输入完成")
                time.sleep(random.uniform(3, 5))

                # 在验证码输入完成后检测是否出现了Turnstile验证
                info("检查是否出现了Turnstile验证...")
                try:
                    turnstile_element = tab.ele("@id=cf-turnstile", timeout=3)
                    if turnstile_element:
                        info("检测到验证码输入后出现Turnstile验证，正在处理...")
                        handle_turnstile(tab)
                except:
                    info("未检测到Turnstile验证，继续下一步")

                break
        except Exception as e:
            info(f"验证码处理失败: {str(e)}")
            return "ERROR"

    info("完成最终验证...")
    handle_turnstile(tab)
    time.sleep(random.uniform(3, 5))
    info("账号注册流程完成")
    return "SUCCESS"


class EmailGenerator:
    def __init__(
        self,
    ):
        # 将密码生成移到这里，避免类定义时执行随机密码生成
        self.default_first_name = self.generate_random_name()
        self.default_last_name = self.generate_random_name()

        # 从配置文件获取域名配置
        self.domains = EMAIL_DOMAINS
        info(f"当前可用域名: {self.domains}")

        self.email = None
        self.password = None

    def generate_random_password(self, length=12):
        """生成随机密码 - 改进密码生成算法，确保包含各类字符"""
        chars = "abcdefghijklmnopqrstuvwxyz"
        upper_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        digits = "0123456789"
        special = "!@#$%^&*"

        # 确保密码包含至少一个大写字母、一个数字和一个特殊字符
        password = [
            random.choice(chars),
            random.choice(upper_chars),
            random.choice(digits),
            random.choice(special),
        ]

        # 添加剩余随机字符
        password.extend(
            random.choices(chars + upper_chars + digits + special, k=length - 4)
        )

        # 打乱密码顺序
        random.shuffle(password)
        return "".join(password)

    def generate_random_name(self, length=6):
        """生成随机用户名"""
        first_letter = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        rest_letters = "".join(
            random.choices("abcdefghijklmnopqrstuvwxyz", k=length - 1)
        )
        return first_letter + rest_letters

    def generate_email(self, length=8):
        """生成随机邮箱地址，使用随机域名"""
        random_str = "".join(
            random.choices("abcdefghijklmnopqrstuvwxyz1234567890", k=length)
        )
        timestamp = str(int(time.time()))[-4:]  # 使用时间戳后4位
        # 随机选择一个域名
        domain = random.choice(self.domains)
        return f"{random_str}@{domain}"

    def get_account_info(self):
        """获取账号信息，确保每次调用都生成新的邮箱和密码"""
        self.email = self.generate_email()
        self.password = self.generate_random_password()
        return {
            "email": self.email,
            "password": self.password,
            "first_name": self.default_first_name.capitalize(),
            "last_name": self.default_last_name.capitalize(),
        }

    def _save_account_info(self, user, token, total_usage):
        try:
            from database import get_session, AccountModel
            import asyncio
            import time

            async def save_to_db():
                info(f"开始保存账号信息: {self.email}")
                async with get_session() as session:
                    # 检查账号是否已存在
                    from sqlalchemy import select

                    result = await session.execute(
                        select(AccountModel).where(AccountModel.email == self.email)
                    )
                    existing_account = result.scalar_one_or_none()

                    if existing_account:
                        info(f"更新现有账号信息 (ID: {existing_account.id})")
                        existing_account.token = token
                        existing_account.user = user
                        existing_account.password = self.password
                        existing_account.usage_limit = str(total_usage)
                        # 如果账号状态是删除，更新为活跃
                        if existing_account.status == "deleted":
                            existing_account.status = "active"
                        # 不更新id，保留原始id值
                    else:
                        info("创建新账号记录")
                        # 生成毫秒级时间戳作为id
                        timestamp_ms = int(time.time() * 1000)
                        account = AccountModel(
                            email=self.email,
                            password=self.password,
                            token=token,
                            user=user,
                            usage_limit=str(total_usage),
                            created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
                            status="active",  # 设置默认状态为活跃
                            id=timestamp_ms,  # 设置毫秒时间戳id
                        )
                        session.add(account)

                    await session.commit()
                    info(f"账号 {self.email} 信息保存成功")
                    return True

            return asyncio.run(save_to_db())
        except Exception as e:
            info(f"保存账号信息失败: {str(e)}")
            return False


def cleanup_and_exit(browser_manager=None, exit_code=0):
    """清理资源并退出程序"""
    try:
        if browser_manager:
            info("正在关闭浏览器")
            if hasattr(browser_manager, "browser"):
                browser_manager.browser.quit()

        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except:
                pass

        info("程序正常退出")
        sys.exit(exit_code)

    except Exception as e:
        info(f"清理退出时发生错误: {str(e)}")
        sys.exit(1)


def main():
    browser_manager = None
    max_retries = REGISTRATION_MAX_RETRIES  # 从配置文件获取
    current_retry = 0

    try:
        email_generator = EmailGenerator()
        browser_manager = BrowserManager()
        browser = browser_manager.init_browser()
        while current_retry < max_retries:
            try:
                account_info = email_generator.get_account_info()
                info(
                    f"初始化账号信息成功 => 邮箱: {account_info['email']}, 用户名: {account_info['first_name']}, 密码: {account_info['password']}"
                )

                signup_tab = browser.new_tab(LOGIN_URL)
                browser.activate_tab(signup_tab)

                signup_tab.run_js("try { turnstile.reset() } catch(e) { }")
                result = sign_up_account(browser, signup_tab, account_info)

                if result == "SUCCESS":
                    token, user = get_cursor_session_token(signup_tab)
                    info(f"获取到账号Token: {token}, 用户: {user}")
                    if token:
                        email_generator._save_account_info(user, token, TOTAL_USAGE)
                        info("注册流程完成")
                        cleanup_and_exit(browser_manager, 0)
                    else:
                        info("获取Cursor会话Token失败")
                        current_retry += 1
                elif result in [
                    "EMAIL_USED",
                    "SIGNUP_RESTRICTED",
                    "VERIFY_FAILED",
                    "EMAIL_GET_CODE_FAILED",
                ]:
                    info(f"遇到问题: {result}，尝试切换邮箱...")
                    continue  # 使用新邮箱重试注册
                else:  # ERROR
                    info("遇到错误，准备重试...")
                    current_retry += 1

                # 关闭标签页，准备下一次尝试
                signup_tab.close()
                time.sleep(2)

            except Exception as e:
                info(f"当前尝试发生错误: {str(e)}")
                current_retry += 1
                time.sleep(2)
                try:
                    # 尝试关闭可能存在的标签页
                    if "signup_tab" in locals():
                        signup_tab.close()
                except:
                    pass

        info(f"达到最大重试次数 {max_retries}，注册失败")
    except Exception as e:
        info(f"主程序错误: {str(e)}")
        info(f"错误详情: {traceback.format_exc()}")
        cleanup_and_exit(browser_manager, 1)
    finally:
        cleanup_and_exit(browser_manager, 1)
