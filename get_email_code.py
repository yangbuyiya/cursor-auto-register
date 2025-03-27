from logger import info, error
import time
import re
import requests
from config import (
    EMAIL_USERNAME,
    EMAIL_DOMAIN,
    EMAIL_PIN,
    EMAIL_VERIFICATION_RETRIES,
    EMAIL_VERIFICATION_WAIT,
)


class EmailVerificationHandler:
    def __init__(self, username=None, domain=None, pin=None):
        self.username = username or EMAIL_USERNAME
        self.domain = domain or EMAIL_DOMAIN
        self.session = requests.Session()
        self.emailExtension = f"@{self.domain}"
        self.pin = pin or EMAIL_PIN
        info(
            f"初始化邮箱验证器成功: {self.username}{self.emailExtension} pin: {self.pin}"
        )

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
        max_retries = max_retries or EMAIL_VERIFICATION_RETRIES
        wait_time = wait_time or EMAIL_VERIFICATION_WAIT
        info(f"开始获取邮箱验证码=>最大重试次数:{max_retries}, 等待时间:{wait_time}")
        for attempt in range(max_retries):
            try:
                code, mail_id = self._get_latest_mail_code(source_email)
                if code:
                    info(f"成功获取验证码: {code}")
                    return code
                if attempt < max_retries - 1:
                    info(
                        f"未找到验证码，{wait_time}秒后重试 ({attempt + 1}/{max_retries})..."
                    )
                    time.sleep(wait_time)
            except Exception as e:
                error(f"获取验证码失败: {str(e)}")
                if attempt < max_retries - 1:
                    info(f"将在{wait_time}秒后重试...")
                    time.sleep(wait_time)

        return None

    # 手动输入验证码
    def _get_latest_mail_code(self, source_email=None):
        info("开始获取邮件列表")
        # 获取邮件列表
        mail_list_url = f"https://tempmail.plus/api/mails?email={self.username}{self.emailExtension}&limit=20&epin={self.pin}"
        try:
            mail_list_response = self.session.get(
                mail_list_url, timeout=10
            )  # 添加超时参数
            mail_list_data = mail_list_response.json()
            time.sleep(0.5)
            if not mail_list_data.get("result"):
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

        # 获取最新邮件的ID
        first_id = mail_list_data.get("first_id")
        if not first_id:
            return None, None
        info(f"开始获取邮件详情: {first_id}")
        # 获取具体邮件内容
        mail_detail_url = f"https://tempmail.plus/api/mails/{first_id}?email={self.username}{self.emailExtension}&epin={self.pin}"
        try:
            mail_detail_response = self.session.get(
                mail_detail_url, timeout=10
            )  # 添加超时参数
            mail_detail_data = mail_detail_response.json()
            time.sleep(0.5)
            if not mail_detail_data.get("result"):
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

        # 如果提供了source_email，确保邮件内容中包含该邮箱地址
        if source_email and source_email.lower() not in mail_text.lower():
            error(f"邮件内容不包含指定的邮箱地址: {source_email}")
        else:
            info(f"邮件内容包含指定的邮箱地址: {source_email}")

        code_match = re.search(r"(?<![a-zA-Z@.])\b\d{6}\b", mail_text)

        if code_match:
            return code_match.group(), first_id
        return None, None

    def _cleanup_mail(self, first_id):
        # 构造删除请求的URL和数据
        delete_url = "https://tempmail.plus/api/mails/"
        payload = {
            "email": f"{self.username}{self.emailExtension}",
            "first_id": first_id,
            "epin": self.pin,
        }

        # 最多尝试5次
        for _ in range(5):
            response = self.session.delete(delete_url, data=payload)
            try:
                result = response.json().get("result")
                if result is True:
                    return True
            except:
                pass

            # 如果失败,等待0.5秒后重试
            time.sleep(0.5)

        return False
