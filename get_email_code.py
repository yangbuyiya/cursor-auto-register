from logger import info, error
# 添加warn函数作为info的包装
def warn(message):
    """警告日志函数"""
    info(f"警告: {message}")

import time
import re
import requests
import os
import uuid
from datetime import datetime
from config import (
    EMAIL_USERNAME,
    EMAIL_DOMAIN,
    EMAIL_PIN,
    EMAIL_VERIFICATION_RETRIES,
    EMAIL_VERIFICATION_WAIT,
    EMAIL_TYPE,
    EMAIL_PROXY_ADDRESS,
    EMAIL_PROXY_ENABLED,
    EMAIL_API,
    EMAIL_CODE_TYPE,
    EMAIL_DOMAINS
)

# 声明全局变量用于存储验证码请求
pending_verification_codes = {}

class EmailVerificationHandler:
    def __init__(self, username=None, domain=None, pin=None, use_proxy=False, custom_email=None):
        self.email = EMAIL_TYPE
        self.custom_email = custom_email
        
        # 如果提供了自定义邮箱，则解析它
        if custom_email and '@' in custom_email:
            username, domain = custom_email.split('@', 1)
        
        self.username = username or EMAIL_USERNAME
        self.domain = domain or EMAIL_DOMAIN
        self.session = requests.Session()
        self.emailApi = EMAIL_API
        self.emailExtension = self.domain
        self.pin = pin or EMAIL_PIN
        if self.pin == "":
            info("注意: 邮箱PIN码为空")
        if self.email == "tempemail":
            info(
                f"初始化邮箱验证器成功: {self.username}@{self.domain} pin: {self.pin}"
            )
        elif self.email == "zmail":
            info(
                f"初始化邮箱验证器成功: {self.emailApi}"
            )
        
        # 添加代理支持
        if use_proxy and EMAIL_PROXY_ENABLED:
            proxy = {
                "http": f"{EMAIL_PROXY_ADDRESS}",
                "https": f"{EMAIL_PROXY_ADDRESS}",
            }
            self.session.proxies.update(proxy)
            info(f"已启用代理: {EMAIL_PROXY_ADDRESS}")

    def check(self):
        # 如果是自定义邮箱场景，跳过邮箱连接检查，直接返回成功
        if self.custom_email is not None:
            info(f"自定义邮箱注册场景 {self.custom_email}，跳过临时邮箱连接检查")
            return True
            
        # 如果有自定义邮箱，优先使用它
        username = self.username
        domain = self.domain
        if self.custom_email and '@' in self.custom_email:
            username, domain = self.custom_email.split('@', 1)
            info(f"使用自定义邮箱进行连接检查: {username}@{domain}")
        
        mail_list_url = f"https://tempmail.plus/api/mails?email={username}%40{domain}&limit=20&epin={self.pin}"
        try:
            # 增加超时时间并添加错误重试
            for retry in range(3):
                try:
                    info(f"请求URL (尝试 {retry+1}/3): {mail_list_url}")
                    mail_list_response = self.session.get(mail_list_url, timeout=30)  # 增加超时时间到30秒
                    mail_list_data = mail_list_response.json()
                    time.sleep(0.5)
                    
                    # 修正判断逻辑：当result为true时才是成功
                    if mail_list_data.get("result") == True:
                        info(f"成功获取邮件列表数据: 共{mail_list_data.get('count', 0)}封邮件")
                        return True
                    else:
                        error(f"API返回结果中无result字段或result为false: {mail_list_data}")
                        return False
                    
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    if retry < 2:  # 如果不是最后一次尝试
                        warn(f"请求超时或连接错误，正在重试... ({retry+1}/3)")
                        time.sleep(2)  # 增加重试间隔
                    else:
                        raise  # 最后一次尝试失败，抛出异常
        except requests.exceptions.Timeout:
            error("获取邮件列表超时")
        except requests.exceptions.ConnectionError:
            error("获取邮件列表连接错误")
            info(f'{mail_list_url}')
        except Exception as e:
            error(f"获取邮件列表发生错误: {str(e)}")
        return False

    def get_verification_code(
        self, source_email=None, max_retries=None, wait_time=None
    ):
        """
        获取验证码，增加了重试机制

        Args:
            max_retries: 最大重试次数
            wait_time: 每次重试间隔时间(秒)

        Returns:
            str: 验证码或None
        """
        # 记录当前的验证码获取模式和邮箱信息
        info(f"验证码获取模式: {EMAIL_CODE_TYPE}, 使用邮箱: {source_email}")
        
        # 通过self.custom_email判断是否为自定义邮箱注册场景，而不是比较source_email
        is_custom_email_scenario = self.custom_email is not None
        
        # 如果是INPUT模式或者是自定义邮箱场景，直接进入手动输入
        if EMAIL_CODE_TYPE == "INPUT" or is_custom_email_scenario:
            if is_custom_email_scenario:
                info("检测到自定义邮箱注册场景，直接使用手动输入验证码模式")
            else:
                info("EMAIL_CODE_TYPE设为INPUT，跳过自动获取，直接手动输入")
            return self.prompt_manual_code(source_email)
        
        # 以下是自动获取验证码的逻辑，只有在EMAIL_CODE_TYPE不是INPUT且不是自定义邮箱场景时才会执行
        max_retries = max_retries or EMAIL_VERIFICATION_RETRIES
        wait_time = wait_time or EMAIL_VERIFICATION_WAIT
        info(f"开始获取邮箱验证码=>最大重试次数:{max_retries}, 等待时间:{wait_time}")
        
        # 验证邮箱类型是否支持
        if self.email not in ["tempemail", "zmail"]:
            error(f"不支持的邮箱类型: {self.email}，支持的类型为: tempemail, zmail")
            warn("自动切换到手动输入模式")
            return self.prompt_manual_code(source_email)
        
        for attempt in range(max_retries):
            try:
                info(f"当前EMail类型为： {self.email}")
                code = None
                mail_id = None
                
                if self.email == "tempemail":
                    code, mail_id = self.get_tempmail_email_code(source_email)
                elif self.email == "zmail":
                    code, mail_id = self.get_zmail_email_code(source_email)
                
                if code:
                    info(f"成功获取验证码: {code}")
                    return code
                elif attempt < max_retries - 1:
                    info(f"未找到验证码，{wait_time}秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    info(f"已达到最大重试次数({max_retries})，未找到验证码")
            except Exception as e:
                error(f"获取验证码失败: {str(e)}")
                if attempt < max_retries - 1:
                    info(f"将在{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    error(f"已达到最大重试次数({max_retries})，获取验证码失败")

        # Web模式下，更新等待验证码请求状态为失败
        web_mode = os.environ.get("CURSOR_AUTO_REGISTER_WEB", "").lower() == "true"
        if web_mode and source_email:
            # 查找该邮箱的待处理验证码请求
            global pending_verification_codes
            for email_id, request_info in list(pending_verification_codes.items()):
                if request_info.get("email") == source_email and request_info.get("status") == "pending":
                    # 更新状态为失败
                    pending_verification_codes[email_id]["status"] = "failed"
                    pending_verification_codes[email_id]["message"] = f"验证码获取失败，已尝试{max_retries}次"
                    info(f"已更新验证码请求 {email_id} 状态为失败")
                    break

        # 在Web模式下，自动获取失败后转为前端手动输入，而不直接返回失败
        if web_mode:
            info("自动获取验证码失败，转为前端手动输入模式")
            return self.prompt_manual_code(source_email)
            
        # 命令行模式下询问手动输入
        response = input("自动获取验证码失败，是否手动输入? (y/n): ").lower()
        if response == 'y':
            return self.prompt_manual_code(source_email)
        return None

    # 手动输入验证码 - 添加前端输入支持
    def prompt_manual_code(self, source_email=None):
        """手动输入验证码，支持前端输入"""
        email_display = source_email if source_email else f"{self.username}@{self.domain}"
        info("=============手动输入验证码模式=============")
        info(f"请查看邮箱 [{email_display}] 中的验证码")
        
        # 检查是否有CURSOR_AUTO_REGISTER_WEB环境变量，表示是否通过Web界面运行
        web_mode = os.environ.get("CURSOR_AUTO_REGISTER_WEB", "").lower() == "true"
        
        if web_mode:
            info("检测到Web模式，使用前端验证码输入")
            return self.prompt_manual_code_web(email_display)
        else:
            info("命令行模式，使用控制台输入验证码")
            info("通常验证码为6位数字，在邮件正文中")
            code = input("请输入收到的验证码: ").strip()
            info(f"已输入验证码: {code}")
            return code
    
    # 前端验证码输入方法
    def prompt_manual_code_web(self, source_email):
        """在Web界面请求验证码输入"""
        # 生成唯一ID
        email_id = str(uuid.uuid4())
        
        # 判断是否是自动获取失败后转为手动输入
        is_auto_failure = EMAIL_CODE_TYPE != "INPUT"
        
        # 存储到等待字典中
        global pending_verification_codes
        pending_verification_codes[email_id] = {
            "email": source_email,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "code": None,
            "auto_failure": is_auto_failure  # 标记是否是自动获取失败后的手动输入
        }
        
        if is_auto_failure:
            info(f"已创建验证码请求 ID: {email_id}，这是在自动获取失败后转为手动输入")
        else:
            info(f"已创建验证码请求 ID: {email_id}，等待前端输入验证码")
        
        # 循环等待验证码输入，最多等待180秒
        start_time = time.time()
        while time.time() - start_time < 180:
            # 检查是否已提交验证码
            if email_id in pending_verification_codes and pending_verification_codes[email_id]["status"] == "submitted":
                code = pending_verification_codes[email_id]["code"]
                info(f"前端已提交验证码: {code}")
                # 删除已使用的记录
                pending_verification_codes.pop(email_id, None)
                return code
            
            # 等待1秒再检查
            time.sleep(1)
        
        # 超时，从等待字典中移除
        pending_verification_codes.pop(email_id, None)
        info("验证码输入超时")
        return None

    def get_tempmail_email_code(self, source_email=None):
        # 如果是自定义邮箱场景，直接返回None，不尝试通过临时邮箱API获取验证码
        if self.custom_email is not None:
            info("自定义邮箱注册场景不应通过临时邮箱API获取验证码，跳过此步骤")
            return None, None
            
        info("开始获取邮件列表")
        
        # 确保在任务注册场景(非自定义邮箱)下使用配置邮箱
        # 仅当source_email存在且与配置邮箱不同时才使用source_email(自定义邮箱场景)
        using_custom_email = (source_email is not None and 
                            '@' in source_email and 
                            source_email != f"{self.username}@{self.domain}")
        
        if using_custom_email:
            username, domain = source_email.split('@', 1)
            mail_list_url = f"https://tempmail.plus/api/mails?email={username}%40{domain}&limit=20&epin={self.pin}"
            info(f"使用自定义邮箱获取验证码: {source_email}")
        else:
            # 任务注册场景，使用配置邮箱
            mail_list_url = f"https://tempmail.plus/api/mails?email={self.username}%40{self.domain}&limit=20&epin={self.pin}"
            info(f"使用配置邮箱获取验证码: {self.username}@{self.domain}")
        
        try:
            # 增加错误重试和超时时间
            for retry in range(3):
                try:
                    info(f"请求邮件列表 (尝试 {retry+1}/3): {mail_list_url}")
                    mail_list_response = self.session.get(
                        mail_list_url, timeout=30
                    )
                    mail_list_data = mail_list_response.json()
                    time.sleep(0.5)
                    
                    # 修正判断逻辑
                    if mail_list_data.get("result") == True:
                        info(f"成功获取邮件列表: 共{mail_list_data.get('count', 0)}封邮件")
                        # 继续处理
                    else:
                        error(f"API返回失败结果: {mail_list_data}")
                        return None, None
                    
                    break  # 成功获取数据，跳出重试循环
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    if retry < 2:  # 如果不是最后一次尝试
                        warn(f"请求超时或连接错误，正在重试... ({retry+1}/3)")
                        time.sleep(2 * (retry + 1))  # 递增的等待时间
                    else:
                        raise  # 最后一次尝试失败，抛出异常
        
            # 获取最新邮件的ID
            first_id = mail_list_data.get("first_id")
            if not first_id:
                return None, None
            info(f"开始获取邮件详情: {first_id}")
            
            # 使用与邮件列表相同的邮箱账号获取邮件详情
            if using_custom_email:
                # 自定义邮箱场景
                mail_detail_url = f"https://tempmail.plus/api/mails/{first_id}?email={username}%40{domain}&epin={self.pin}"
            else:
                # 任务注册场景，使用配置邮箱
                mail_detail_url = f"https://tempmail.plus/api/mails/{first_id}?email={self.username}%40{self.domain}&epin={self.pin}"
            
            try:
                mail_detail_response = self.session.get(
                    mail_detail_url, timeout=10
                )  # 添加超时参数
                mail_detail_data = mail_detail_response.json()
                time.sleep(0.5)
                if mail_detail_data.get("result") == False:
                    error(f"获取邮件详情失败: {mail_detail_data}")
                    return None, None
            except requests.exceptions.Timeout:
                error("获取邮件详情超时")
                return None, None
            except requests.exceptions.ConnectionError:
                error("获取邮件详情连接错误")
                return None, None
            except Exception as e:
                error(f"获取邮件详情发生错误: {str(e)}")
                return None, None

            # 从邮件文本中提取6位数字验证码
            mail_text = mail_detail_data.get("text", "")

            # 在自定义邮箱场景下检查邮件内容包含该邮箱，任务注册场景不需要检查
            if using_custom_email and source_email and source_email.lower() not in mail_text.lower():
                error(f"邮件内容不包含指定的邮箱地址: {source_email}")
            else:
                if using_custom_email:
                    info(f"邮件内容包含指定的邮箱地址: {source_email}")
                else:
                    info(f"使用配置邮箱获取验证码，不需要检查邮件内容")

            code_match = re.search(r"(?<![a-zA-Z@.])\b\d{6}\b", mail_text)

            if code_match:
                # 清理邮件时使用正确的邮箱
                self._cleanup_mail(first_id, source_email if using_custom_email else None)
                return code_match.group(), first_id
            return None, None
        except requests.exceptions.Timeout:
            error("获取邮件列表超时")
            return None, None
        except requests.exceptions.ConnectionError:
            error("获取邮件列表连接错误")
            return None, None
        except Exception as e:
            error(f"获取邮件列表发生错误: {str(e)}")
            return None, None

    def _cleanup_mail(self, first_id, source_email=None):
        # 如果提供了source_email且不为空，则判断是否为自定义邮箱场景
        using_custom_email = (source_email is not None and 
                            '@' in source_email and 
                            source_email != f"{self.username}@{self.domain}")
        
        # 设置用于清理邮件的用户名和域名
        if using_custom_email:
            # 自定义邮箱场景
            username, domain = source_email.split('@', 1)
            info(f"使用自定义邮箱清理邮件: {username}@{domain}")
        else:
            # 任务注册场景，使用配置邮箱
            username = self.username
            domain = self.domain
            info(f"使用配置邮箱清理邮件: {username}@{domain}")
        
        # 构造删除请求的URL和数据
        delete_url = "https://tempmail.plus/api/mails/"
        payload = {
            "email": f"{username}@{domain}",
            "first_id": first_id,
            "epin": self.pin,
        }

        # 最多尝试3次
        for _ in range(3):
            response = self.session.delete(delete_url, data=payload)
            try:
                result = response.json().get("result")
                if result is True:
                    return True
            except:
                pass

            # 如果失败,等待0.2秒后重试
            time.sleep(0.2)

        return False

    # 如果是zmail 需要先创建邮箱
    def create_zmail_email(account_info):
        # 如果邮箱类型是zmail 需要先创建邮箱
        session = requests.Session()
        if EMAIL_PROXY_ENABLED:
            proxy = {
                "http": f"{EMAIL_PROXY_ADDRESS}",
                "https": f"{EMAIL_PROXY_ADDRESS}",
            }
            session.proxies.update(proxy)
        # 创建临时邮箱URL
        create_url = f"{EMAIL_API}/api/mailboxes"
        username = account_info["email"].split("@")[0]
        # 生成临时邮箱地址
        payload = {
            "address": f"{username}",
            "expiresInHours": 24,
        }
        # 发送POST请求创建临时邮箱
        try:
            create_response = session.post(
                create_url, json=payload, timeout=100
            )  # 添加超时参数
            info(f"创建临时邮箱成功: {create_response.status_code}")
            create_data = create_response.json()
            info(f"创建临时邮箱返回数据: {create_data}")
            # 检查创建邮箱是否成功
            time.sleep(0.5)
            if create_data.get("success") is True or create_data.get('error') == '邮箱地址已存在':
                info(f"邮箱创建成功: {create_data}")
            else:
                error(f"邮箱创建失败: {create_data}")
                return None, None
        except requests.exceptions.Timeout:
            error("创建临时邮箱超时", create_url)
            return None, None
        info(f"创建临时邮箱成功: {create_data}, 返回值: {create_data}")
            
    # 获取zmail邮箱验证码
    def get_zmail_email_code(self, source_email=None):
        # 如果是自定义邮箱场景，直接返回None，不尝试通过zmail API获取验证码
        if self.custom_email is not None:
            info("自定义邮箱注册场景不应通过zmail API获取验证码，跳过此步骤")
            return None, None
            
        info("开始获取邮件列表")
        
        # 确保在任务注册场景(非自定义邮箱)下使用配置邮箱
        # 仅当source_email存在且与配置邮箱不同时才使用source_email(自定义邮箱场景)
        using_custom_email = (source_email is not None and 
                            '@' in source_email and 
                            source_email != f"{self.username}@{self.domain}")
        
        # 获取邮件列表
        if using_custom_email:
            # 自定义邮箱场景
            email_to_use = source_email
            info(f"使用自定义邮箱获取验证码: {email_to_use}")
        else:
            # 任务注册场景，使用配置邮箱
            email_to_use = f"{self.username}@{self.domain}"
            info(f"使用配置邮箱获取验证码: {email_to_use}")
        
        if '@' not in email_to_use:
            error(f"邮箱格式错误: {email_to_use}")
            return None, None
        
        username = email_to_use.split("@")[0]
        info(f"使用邮箱获取验证码: {email_to_use}, 用户名: {username}")
        
        mail_list_url = f"{EMAIL_API}/api/mailboxes/{username}/emails"
        
        if EMAIL_PROXY_ENABLED:
            proxy = {
                "http": f"{EMAIL_PROXY_ADDRESS}",
                "https": f"{EMAIL_PROXY_ADDRESS}",
            }
            self.session.proxies.update(proxy)
        try:
            mail_list_response = self.session.get(
                mail_list_url, timeout=10000
            )  # 添加超时参数
            mail_list_data = mail_list_response.json()
            time.sleep(2)
            if not mail_list_data.get("emails"):
                return None, None
        except requests.exceptions.Timeout:
            error("获取邮件列表超时")
            return None, None
        except requests.exceptions.ConnectionError:
            error("获取邮件列表连接错误")
            return None, None
        except Exception as e:
            error(f"获取邮件列表发生错误: {str(e)}")
            return None, None

        # 获取最新邮件的ID、
        mail_detail_data_len = len(mail_list_data["emails"])
        if mail_detail_data_len == 0:
            return None, None
        mail_list_data = mail_list_data["emails"][0]
        # 获取最新邮件的ID
        mail_id = mail_list_data.get("id")
        if not mail_id:
            return None, None
        # 获取具体邮件内容
        mail_detail_url = f"{EMAIL_API}/api/emails/{mail_id}"
        returnData = ''
        try:
            mail_detail_response = self.session.get(
                mail_detail_url, timeout=10
            )  # 添加超时参数
            returnData = mail_detail_response.json()
            time.sleep(2)
        except requests.exceptions.Timeout:
            error("获取邮件详情超时")
            return None, None
        except requests.exceptions.ConnectionError:
            error("获取邮件详情连接错误")
            return None, None
        except Exception as e:
            error(f"获取邮件详情发生错误: {str(e)}")
            return None, None

        # 从邮件文本中提取6位数字验证码\
        mail_text = returnData.get("email")
        mail_text = mail_text.get("textContent")
        # 如果提供了source_email，确保邮件内容中包含该邮箱地址
        if source_email and source_email.lower() not in mail_text.lower():
            error(f"邮件内容不包含指定的邮箱地址: {source_email}")
        else:
            info(f"邮件内容包含指定的邮箱地址: {source_email}")

        code_match = re.search(r"(?<![a-zA-Z@.])\b\d{6}\b", mail_text)
        info(f"验证码匹配结果: {code_match}")
        # 如果找到验证码, 返回验证码和邮件ID
        if code_match:
            return code_match.group(), mail_id
        else:
            error("未找到验证码")
            return None, None

    def diagnose_email_setup(self):
        """诊断邮箱设置并显示可能的问题"""
        issues = []
        
        # 检查邮箱类型
        if self.email not in ["tempemail", "zmail"]:
            issues.append(f"不支持的邮箱类型: {self.email}")
        
        # 检查邮箱用户名
        if not self.username:
            issues.append("邮箱用户名为空")
        
        # 检查域名
        if not self.domain:
            issues.append("邮箱域名为空")
        
        # 检查获取验证码类型
        if EMAIL_CODE_TYPE == "INPUT":
            issues.append("EMAIL_CODE_TYPE设为INPUT，将跳过自动获取")
        
        info("----- 邮箱设置诊断 -----")
        info(f"邮箱类型: {self.email}")
        info(f"邮箱地址: {self.username}@{self.domain}")
        info(f"验证码获取方式: {EMAIL_CODE_TYPE}")
        
        if issues:
            warn("发现以下问题:")
            for issue in issues:
                warn(f"- {issue}")
        else:
            info("未发现明显问题")
        
        return issues

if __name__ == "__main__":
    import argparse
    
    # 添加代码检查并显示配置值
    info(f"当前配置: EMAIL_TYPE={EMAIL_TYPE}, EMAIL_CODE_TYPE={EMAIL_CODE_TYPE}")
    
    # 如果EMAIL_CODE_TYPE为INPUT则警告用户
    if EMAIL_CODE_TYPE == "INPUT":
        warn("EMAIL_CODE_TYPE设为INPUT将会跳过自动获取验证码，直接手动输入")
        # 给用户选择是否临时更改为自动模式
        response = input("是否临时更改为自动模式? (y/n): ").lower()
        if response == 'y':
            EMAIL_CODE_TYPE = "AUTO"
            info("已临时更改为自动模式")
    
    parser = argparse.ArgumentParser(description='测试邮箱验证码获取功能')
    parser.add_argument('--username', default=EMAIL_USERNAME, help='邮箱用户名')
    parser.add_argument('--domain', default=EMAIL_DOMAIN, help='邮箱域名')
    parser.add_argument('--pin', default=EMAIL_PIN, help='邮箱PIN码（可以为空）')
    parser.add_argument('--source', help='来源邮箱（可选）')
    parser.add_argument('--type', default=EMAIL_TYPE, choices=['tempemail', 'zmail'], help='邮箱类型')
    parser.add_argument('--proxy', action='store_true', help='是否使用代理')
    args = parser.parse_args()
    
    # 覆盖全局EMAIL_TYPE以便测试不同类型
    from config import EMAIL_TYPE
    if args.type != EMAIL_TYPE:
        info(f"覆盖EMAIL_TYPE从{EMAIL_TYPE}到{args.type}")
        EMAIL_TYPE = args.type
    
    # 创建邮箱验证处理器
    handler = EmailVerificationHandler(
        username=args.username, 
        domain=args.domain, 
        pin=args.pin,
        use_proxy=args.proxy
    )
    
    # 诊断邮箱设置
    handler.diagnose_email_setup()
    
    # 测试检查邮箱
    info("测试检查邮箱...")
    check_result = handler.check()
    info(f"检查结果: {'成功' if check_result else '失败'}")
    
    # 测试获取验证码
    info("测试获取验证码...")
    code = handler.get_verification_code(source_email=args.source)
    
    if code:
        info(f"成功获取验证码: {code}")
    else:
        error("获取验证码失败")
    
    info("测试完成")
