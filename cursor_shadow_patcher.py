import os
import re
import random
import shutil
import pathlib
import platform
from uuid import uuid4
from logger import info, warning, error

from config import CURSOR_PATH


# 颜色常量定义，保留用于日志输出
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[96m"
PURPLE = "\033[95m"
RESET = "\033[0m"

SYSTEM = platform.system()
if SYSTEM not in ("Windows", "Linux", "Darwin"):
    raise OSError(f"不支持的操作系统: {SYSTEM}")


def uuid():
    """生成随机UUID"""
    return str(uuid4())


def path(path_str):
    """获取绝对路径"""
    return pathlib.Path(path_str).resolve()


def randomuuid(randomuuid_str):
    """获取随机UUID，如果提供则使用提供的值"""
    if not randomuuid_str:
        randomuuid_str = uuid()
    return randomuuid_str


def random_mac():
    """生成随机MAC地址"""
    mac = [
        0x00,
        0x16,
        0x3E,
        random.randint(0x00, 0x7F),
        random.randint(0x00, 0xFF),
        random.randint(0x00, 0xFF),
    ]
    return ":".join(map(lambda x: "%02x" % x, mac))


def load(file_path: pathlib.Path):
    """加载文件内容"""
    with open(file_path, "rb") as f:
        return f.read()


def save(file_path: pathlib.Path, data: bytes):
    """保存文件内容"""
    with open(file_path, "wb") as f:
        f.write(data)


def backup(file_path: pathlib.Path):
    """备份文件"""
    backup_path = file_path.with_suffix(file_path.suffix + ".bak")
    if not backup_path.exists():
        shutil.copy2(file_path, backup_path)
        print(f"已备份 {file_path} -> {backup_path}")


def replace(data: bytes, pattern: str, replace_str: str, probe: str = None) -> bytes:
    """替换文件内容"""
    pattern_bytes = pattern.encode() if isinstance(pattern, str) else pattern
    replace_bytes = (
        replace_str.encode() if isinstance(replace_str, str) else replace_str
    )

    if probe:
        probe_bytes = probe.encode() if isinstance(probe, str) else probe
        if re.search(probe_bytes, data):
            print("检测到已经被修补的代码，跳过...")
            return data

    return re.sub(pattern_bytes, replace_bytes, data)


def find_main_js():
    """查找Cursor的main.js文件"""
    error(f"SYSTEM: {SYSTEM}")
    if SYSTEM == "Windows":
        localappdata = os.getenv("LOCALAPPDATA")
        if not localappdata:
            raise OSError("环境变量 %LOCALAPPDATA% 不存在")

        # 使用本地变量保存路径
        cursor_path = CURSOR_PATH
        if not cursor_path:
            error("当前windows系统, 环境变量 CURSOR_PATH 不存在，使用默认路径")
            cursor_path = os.getenv("LOCALAPPDATA", "")
        else:
            info(f"当前windows系统, CURSOR_PATH: {cursor_path}")

        # 常见的Cursor安装路径
        paths = [
            path(os.path.join(cursor_path, "resources", "app", "out", "main.js")),
            path(
                os.path.join(
                    localappdata,
                    "Programs",
                    "cursor",
                    "resources",
                    "app",
                    "out",
                    "main.js",
                )
            ),
            path(
                os.path.join(
                    localappdata, "cursor", "resources", "app", "out", "main.js"
                )
            ),
        ]

        for p in paths:
            info(f"检查路径: {p}")
            if p.exists():
                info(f"找到main.js: {p}")
                return p
            else:
                warning(f"路径不存在: {p}")

    elif SYSTEM == "Darwin":  # macOS
        paths = [
            path("/Applications/Cursor.app/Contents/Resources/app/out/main.js"),
            path(
                os.path.expanduser(
                    "~/Applications/Cursor.app/Contents/Resources/app/out/main.js"
                )
            ),
        ]

        for p in paths:
            if p.exists():
                return p

    elif SYSTEM == "Linux":
        # Linux上常见的安装路径
        paths = [
            path("/usr/share/cursor/resources/app/out/main.js"),
            path(os.path.expanduser("~/.local/share/cursor/resources/app/out/main.js")),
        ]

        for p in paths:
            if p.exists():
                return p

    raise FileNotFoundError("无法找到Cursor的main.js文件，请手动指定路径")


def patch_cursor(
    js_path=None, machine_id=None, mac_addr=None, sqm_id=None, dev_id=None
):
    """
    修补Cursor的main.js文件，替换机器ID等识别信息

    参数:
        js_path: main.js文件路径，如果为None则自动查找
        machine_id: 机器ID，如果为None则随机生成
        mac_addr: MAC地址，如果为None则随机生成
        sqm_id: Windows SQM ID，如果为None则使用空字符串
        dev_id: 设备ID，如果为None则随机生成

    返回:
        bool: 是否成功
    """
    try:
        # 查找main.js文件
        if not js_path:
            js_path = find_main_js()
        else:
            js_path = path(js_path)

        # 如果找不到main.js文件
        if not js_path.exists():
            print(f"错误: 找不到文件 {js_path}")
            return False

        print(f"找到main.js文件: {js_path}")

        # 随机生成ID
        machine_id = randomuuid(machine_id)
        mac_addr = mac_addr or random_mac()
        sqm_id = sqm_id or ""
        dev_id = randomuuid(dev_id)

        # 加载文件内容
        data = load(js_path)

        # 备份文件
        backup(js_path)

        # 替换机器ID
        data = replace(
            data,
            r"=.{0,50}timeout.{0,10}5e3.*?,",
            f'=/*csp1*/"{machine_id}"/*1csp*/,',
            r"=/\*csp1\*/.*?/\*1csp\*/,",
        )

        # 替换MAC地址
        data = replace(
            data,
            r"(function .{0,50}\{).{0,300}Unable to retrieve mac address.*?(\})",
            f'\\1return/*csp2*/"{mac_addr}"/*2csp*/;\\2',
            r"()return/\*csp2\*/.*?/\*2csp\*/;()",
        )

        # 替换SQM ID
        data = replace(
            data,
            r'return.{0,50}\.GetStringRegKey.*?HKEY_LOCAL_MACHINE.*?MachineId.*?\|\|.*?""',
            f'return/*csp3*/"{sqm_id}"/*3csp*/',
            r"return/\*csp3\*/.*?/\*3csp\*/",
        )

        # 替换设备ID
        data = replace(
            data,
            r"return.{0,50}vscode\/deviceid.*?getDeviceId\(\)",
            f'return/*csp4*/"{dev_id}"/*4csp*/',
            r"return/\*csp4\*/.*?/\*4csp\*/",
        )

        # 保存修改后的文件
        save(js_path, data)

        print(f"成功修补 {js_path}")
        print(f"机器ID: {machine_id}")
        print(f"MAC地址: {mac_addr}")
        print(f"SQM ID: {sqm_id}")
        print(f"设备ID: {dev_id}")

        return True

    except Exception as e:
        print(f"错误: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


class CursorShadowPatcher:
    """Cursor机器标识修改器"""

    @staticmethod
    def reset_machine_ids():
        """重置所有机器标识"""
        return patch_cursor()


if __name__ == "__main__":
    # 作为独立脚本运行时，执行交互式修补
    print(f"\n{'=' * 50}")
    print("Cursor 机器标识重置工具 (Shadow Patch 增强版)")
    print(f"{'=' * 50}")

    js_path = input("请输入main.js路径 (留空=自动检测): ")
    machine_id = input("机器ID (留空=随机生成): ")
    mac_addr = input("MAC地址 (留空=随机生成): ")
    sqm_id = input("Windows SQM ID (留空=使用空值): ")
    dev_id = input("设备ID (留空=随机生成): ")

    success = patch_cursor(js_path, machine_id, mac_addr, sqm_id, dev_id)

    if success:
        print(f"\n{'=' * 50}")
        print("修补成功!")
    else:
        print(f"\n{'=' * 50}")
        print("修补失败!")

    input("按回车键退出...")
