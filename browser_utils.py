from DrissionPage import ChromiumOptions, Chromium
import sys
import os
from logger import info, warning, error
from config import (
    BROWSER_USER_AGENT,
    BROWSER_PATH,
    BROWSER_HEADLESS,
    BROWSER_PROXY,
    DYNAMIC_USERAGENT
)
import random
import time

# 用户代理列表 - 按平台分类
USER_AGENTS = {
    'windows': [
        # Chrome Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        # Edge Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.76',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.47',
        # Firefox Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
    ],
    'macos': [
        # Chrome macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        # Safari macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        # Firefox macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/118.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0',
    ],
    'linux': [
        # Chrome Linux
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        # Firefox Linux
        'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/118.0',
        'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0',
    ]
}

def get_random_user_agent():
    """根据当前平台获取随机用户代理"""
    platform = 'windows'
    if sys.platform == 'darwin':
        platform = 'macos'
    elif sys.platform.startswith('linux'):
        platform = 'linux'

    # 获取当前平台的UA列表
    ua_list = USER_AGENTS.get(platform, USER_AGENTS['windows'])
    return random.choice(ua_list)

class BrowserManager:
    def __init__(self):
        self.browser = None

    def init_browser(self):
        try:
            info("正在初始化浏览器...")
            co = ChromiumOptions()

            if BROWSER_PROXY:
                co.set_proxy(BROWSER_PROXY)

            # 如果配置了特定的浏览器路径，则使用
            if BROWSER_PATH and os.path.exists(BROWSER_PATH):
                co.set_browser_path(BROWSER_PATH)
                info(f"使用自定义浏览器路径: {BROWSER_PATH}")

            try:
                extension_path = self._get_extension_path()
                co.add_extension(extension_path)
            except FileNotFoundError as e:
                info(f"警告: {e}")

            # 设置User-Agent
            if DYNAMIC_USERAGENT:
                # 随机选择一个User-Agent
                user_agent = get_random_user_agent()
                info(f"使用动态User-Agent: {user_agent}")
                co.set_user_agent(user_agent)
            else:
                info(f"使用固定User-Agent: {BROWSER_USER_AGENT}")
                co.set_user_agent(BROWSER_USER_AGENT)

            co.set_pref("credentials_enable_service", False)
            co.set_argument("--hide-crash-restore-bubble")
            # 禁用自动化特征（关键参数）
            co.set_argument("--disable-blink-features=AutomationControlled")
            co.set_argument("--disable-features=AutomationControlled")
            co.set_argument("--disable-automation-extension")

            # 随机化指纹参数
            co.set_pref("webgl.vendor", "NVIDIA Corporation")
            co.set_pref(
                "webgl.renderer",
                "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0)",
            )
            co.set_pref("navigator.plugins.length", 5)
            co.set_pref("navigator.hardwareConcurrency", 8)

            # 覆盖自动化特征（关键）
            co.set_pref("dom.webdriver.enabled", False)
            co.set_pref("useAutomationExtension", False)

            # 设置时区参数
            co.set_argument("--timezone=Asia/Shanghai")
            co.set_pref("timezone.override", "Asia/Shanghai")

            # 设置更真实的屏幕参数
            co.set_pref("screen.width", 1920)
            co.set_pref("screen.height", 1080)
            co.set_pref("screen.pixelDepth", 24)
            co.auto_port()
            co.headless(BROWSER_HEADLESS)  # 生产环境使用无头模式

            # Mac 系统特殊处理
            if sys.platform == "darwin" or sys.platform == "linux":
                co.set_argument("--no-sandbox")
                co.set_argument("--disable-gpu")

            self.browser = Chromium(co)
            info("浏览器初始化成功")
        except Exception as e:
            error(f"浏览器初始化失败: {str(e)}")
        return self.browser
    def _get_extension_path(self):
        """获取插件路径"""
        root_dir = os.getcwd()
        extension_path = os.path.join(root_dir, "turnstilePatch")

        if hasattr(sys, "_MEIPASS"):
            extension_path = os.path.join(sys._MEIPASS, "turnstilePatch")

        if not os.path.exists(extension_path):
            raise FileNotFoundError(f"插件不存在: {extension_path}")
        info(f"插件路径: {extension_path}")
        return extension_path

    def quit(self):
        info("正在关闭浏览器...")
        try:
            if self.browser:
                self.browser.quit()
            info("浏览器已关闭")
        except Exception as e:
            error(f"关闭浏览器出错: {str(e)}")
