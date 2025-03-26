import os
import sys
import json
import uuid
import hashlib
import shutil
import pathlib
import re
import random
import platform
import subprocess
from colorama import Fore, Style, init

# 初始化colorama
init()

# 定义emoji和颜色常量
EMOJI = {
    "FILE": "📄",
    "BACKUP": "💾",
    "SUCCESS": "✅",
    "ERROR": "❌",
    "INFO": "ℹ️",
    "RESET": "🔄",
    "PATCH": "🛠️",
    "DOWNLOAD": "📥",
}


class MachineIDResetter:
    def __init__(self):
        # 判断操作系统
        self.system = platform.system()
        if sys.platform == "win32":  # Windows
            appdata = os.getenv("APPDATA")
            if appdata is None:
                raise EnvironmentError("APPDATA 环境变量未设置")
            self.db_path = os.path.join(
                appdata, "Cursor", "User", "globalStorage", "storage.json"
            )
            self.js_path = self._find_main_js_path()
        elif sys.platform == "darwin":  # macOS
            self.db_path = os.path.abspath(
                os.path.expanduser(
                    "~/Library/Application Support/Cursor/User/globalStorage/storage.json"
                )
            )
            self.js_path = self._find_main_js_path()
        elif sys.platform == "linux":  # Linux 和其他类Unix系统
            self.db_path = os.path.abspath(
                os.path.expanduser("~/.config/Cursor/User/globalStorage/storage.json")
            )
            self.js_path = None  # 在Linux上通过AppImage处理
            self.appimage_path = None
            self.appimage_extracted_path = None
        else:
            raise NotImplementedError(f"不支持的操作系统: {sys.platform}")

    def _safe_path(self, path_str):
        """安全地处理路径，返回Path对象"""
        if isinstance(path_str, str):
            path_str = path_str.strip().strip("'\"")
        return pathlib.Path(path_str).resolve()

    def _find_main_js_path(self):
        """查找Cursor的main.js文件路径"""
        if sys.platform == "win32":  # Windows
            localappdata = os.getenv("LOCALAPPDATA")
            if not localappdata:
                return None
            js_path = os.path.join(
                localappdata, "Programs", "cursor", "resources", "app", "out", "main.js"
            )
            if os.path.exists(js_path):
                return js_path
        elif sys.platform == "darwin":  # macOS
            js_path = "/Applications/Cursor.app/Contents/Resources/app/out/main.js"
            if os.path.exists(js_path):
                return js_path
        return None
        
    def _find_appimage_path(self):
        """在Linux系统中查找Cursor的AppImage文件"""
        if sys.platform != "linux":
            return None
            
        print(f"{Fore.CYAN}{EMOJI['INFO']} 正在查找Cursor AppImage...{Style.RESET_ALL}")
        
        # 搜索常见路径
        search_paths = [
            self._safe_path("/usr/local/bin"),
            self._safe_path("/opt"),
            self._safe_path("~/Applications").expanduser(),
            self._safe_path("~/.local/bin").expanduser(),
            self._safe_path("~/Downloads").expanduser(),
            self._safe_path("~/Desktop").expanduser(),
            self._safe_path("~").expanduser(),
            self._safe_path("."),
        ]
        
        # 添加PATH环境变量中的路径
        paths = os.environ.get("PATH", "").split(os.pathsep)
        for p in paths:
            try:
                search_paths.append(self._safe_path(p))
            except:
                continue
                
        # 在所有路径中查找
        for search_path in search_paths:
            if not search_path.exists() or not search_path.is_dir():
                continue
                
            try:
                for file in search_path.iterdir():
                    if not file.is_file():
                        continue
                    name = file.name.lower()
                    if (
                        name.startswith("cursor")
                        and not name[6:7].isalpha()
                        and name.endswith(".appimage")
                    ):
                        print(f"{Fore.GREEN}{EMOJI['SUCCESS']} 找到Cursor AppImage: {file}{Style.RESET_ALL}")
                        return file
            except Exception as e:
                print(f"{Fore.YELLOW}{EMOJI['INFO']} 搜索路径 {search_path} 时出错: {str(e)}{Style.RESET_ALL}")
                continue
                
        return None

    def _extract_appimage(self, appimage_path):
        """解包AppImage文件"""
        if not appimage_path.exists():
            print(f"{Fore.RED}{EMOJI['ERROR']} AppImage文件不存在: {appimage_path}{Style.RESET_ALL}")
            return None
            
        print(f"{Fore.CYAN}{EMOJI['INFO']} 正在解包AppImage...{Style.RESET_ALL}")
        
        # 将AppImage拷贝到当前目录（如果它不在当前目录）
        current_dir = self._safe_path(".")
        if appimage_path.parent != current_dir:
            local_appimage = current_dir / appimage_path.name
            shutil.copy2(appimage_path, local_appimage)
            appimage_path = local_appimage
            
        # 确保AppImage是可执行的
        os.system(f"chmod +x {appimage_path}")
        
        # 解包AppImage
        extract_dir = current_dir / "squashfs-root"
        if extract_dir.exists():
            print(f"{Fore.YELLOW}{EMOJI['INFO']} 发现之前的解包目录，正在删除...{Style.RESET_ALL}")
            shutil.rmtree(extract_dir)
            
        print(f"{Fore.CYAN}{EMOJI['INFO']} 执行解包命令: {appimage_path} --appimage-extract{Style.RESET_ALL}")
        result = os.system(f"{appimage_path} --appimage-extract")
        
        if result != 0:
            print(f"{Fore.RED}{EMOJI['ERROR']} 解包AppImage失败{Style.RESET_ALL}")
            return None
            
        # 如果AppImage是复制过来的，清理临时文件
        if appimage_path.parent == current_dir and appimage_path != self.appimage_path:
            os.remove(appimage_path)
            
        print(f"{Fore.GREEN}{EMOJI['SUCCESS']} AppImage解包成功 -> {extract_dir}{Style.RESET_ALL}")
        return extract_dir

    def _find_js_in_extracted_appimage(self, extract_dir):
        """在解包后的AppImage中查找main.js文件"""
        if not extract_dir.exists():
            return None
            
        # 常见路径
        js_paths = [
            extract_dir / "resources" / "app" / "out" / "main.js",
            extract_dir / "usr" / "share" / "cursor" / "resources" / "app" / "out" / "main.js",
        ]
        
        for js_path in js_paths:
            if js_path.exists():
                print(f"{Fore.GREEN}{EMOJI['SUCCESS']} 在AppImage中找到main.js: {js_path}{Style.RESET_ALL}")
                return js_path
                
        print(f"{Fore.RED}{EMOJI['ERROR']} 在解包的AppImage中未找到main.js{Style.RESET_ALL}")
        return None

    def _repack_appimage(self, extracted_path, appimage_path):
        """重新打包AppImage"""
        print(f"{Fore.CYAN}{EMOJI['INFO']} 正在重新打包AppImage...{Style.RESET_ALL}")
        
        # 检查是否安装了wget
        if not shutil.which("wget"):
            print(f"{Fore.RED}{EMOJI['ERROR']} 未找到wget，请先安装{Style.RESET_ALL}")
            return False
            
        # 检查是否有appimagetool
        current_dir = self._safe_path(".")
        appimagetool = current_dir / "appimagetool"
        appimagetool_downloading = current_dir / "appimagetool_downloading"
        
        if appimagetool_downloading.exists():
            os.remove(appimagetool_downloading)
            
        # 如果没有appimagetool，则下载
        if not appimagetool.exists():
            print(f"{Fore.YELLOW}{EMOJI['INFO']} 未找到appimagetool，需要下载{Style.RESET_ALL}")
            
            print(f"{Fore.CYAN}{EMOJI['DOWNLOAD']} 正在下载appimagetool...{Style.RESET_ALL}")
            download_cmd = f"wget https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage -O {appimagetool_downloading}"
            result = os.system(download_cmd)
            
            if result != 0:
                print(f"{Fore.RED}{EMOJI['ERROR']} 下载失败，请手动下载appimagetool并放置在当前目录{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}{EMOJI['INFO']} 下载链接: https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage{Style.RESET_ALL}")
                return False
                
            # 使下载的工具可执行并重命名
            os.system(f"chmod +x {appimagetool_downloading}")
            os.rename(appimagetool_downloading, appimagetool)
            print(f"{Fore.GREEN}{EMOJI['SUCCESS']} appimagetool下载成功{Style.RESET_ALL}")
            
        # 备份原始AppImage
        self._backup_file(appimage_path)
        
        # 使用appimagetool重新打包
        pack_cmd = f"{appimagetool} {extracted_path} {appimage_path}"
        print(f"{Fore.CYAN}{EMOJI['INFO']} 正在打包: {pack_cmd}{Style.RESET_ALL}")
        result = os.system(pack_cmd)
        
        if result != 0:
            print(f"{Fore.RED}{EMOJI['ERROR']} 重新打包AppImage失败{Style.RESET_ALL}")
            return False
            
        print(f"{Fore.GREEN}{EMOJI['SUCCESS']} AppImage重新打包成功，已替换{appimage_path}{Style.RESET_ALL}")
        
        # 清理临时目录
        shutil.rmtree(extracted_path)
        print(f"{Fore.GREEN}{EMOJI['SUCCESS']} 已清理临时目录 {extracted_path}{Style.RESET_ALL}")
        
        return True

    def generate_new_ids(self):
        """生成新的机器ID"""
        # 生成新的UUID
        dev_device_id = str(uuid.uuid4())

        # 生成新的machineId (64个字符的十六进制)
        machine_id = hashlib.sha256(os.urandom(32)).hexdigest()

        # 生成新的macMachineId (128个字符的十六进制)
        mac_machine_id = hashlib.sha512(os.urandom(64)).hexdigest()

        # 生成新的sqmId
        sqm_id = "{" + str(uuid.uuid4()).upper() + "}"

        return {
            "telemetry.devDeviceId": dev_device_id,
            "telemetry.macMachineId": mac_machine_id,
            "telemetry.machineId": machine_id,
            "telemetry.sqmId": sqm_id,
        }

    def generate_random_mac(self):
        """生成一个随机的MAC地址"""
        mac = ""
        while not mac or mac in ("00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff", "ac:de:48:00:11:22"):
            mac = ":".join([f"{random.randint(0, 255):02X}" for _ in range(6)])
        return mac

    def reset_storage_json(self):
        """重置storage.json中的机器ID"""
        try:
            print(f"{Fore.CYAN}{EMOJI['INFO']} 正在检查配置文件...{Style.RESET_ALL}")

            # 检查文件是否存在
            if not os.path.exists(self.db_path):
                print(
                    f"{Fore.RED}{EMOJI['ERROR']} 配置文件不存在: {self.db_path}{Style.RESET_ALL}"
                )
                return False

            # 检查文件权限
            if not os.access(self.db_path, os.R_OK | os.W_OK):
                print(
                    f"{Fore.RED}{EMOJI['ERROR']} 无法读写配置文件，请检查文件权限！{Style.RESET_ALL}"
                )
                print(
                    f"{Fore.RED}{EMOJI['ERROR']} 如果你使用过 go-cursor-help 来修改 ID; 请修改文件只读权限 {self.db_path} {Style.RESET_ALL}"
                )
                return False

            # 读取现有配置
            print(f"{Fore.CYAN}{EMOJI['FILE']} 读取当前配置...{Style.RESET_ALL}")
            with open(self.db_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 生成新的ID
            print(f"{Fore.CYAN}{EMOJI['RESET']} 生成新的机器标识...{Style.RESET_ALL}")
            new_ids = self.generate_new_ids()

            # 更新配置
            config.update(new_ids)

            # 备份原文件
            backup_path = f"{self.db_path}.bak"
            print(f"{Fore.CYAN}{EMOJI['BACKUP']} 备份原配置到 {backup_path}...{Style.RESET_ALL}")
            shutil.copy2(self.db_path, backup_path)

            # 保存新配置
            print(f"{Fore.CYAN}{EMOJI['FILE']} 保存新配置...{Style.RESET_ALL}")
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)

            print(f"{Fore.GREEN}{EMOJI['SUCCESS']} 机器标识重置成功！{Style.RESET_ALL}")
            print(f"\n{Fore.CYAN}新的机器标识:{Style.RESET_ALL}")
            for key, value in new_ids.items():
                print(f"{EMOJI['INFO']} {key}: {Fore.GREEN}{value}{Style.RESET_ALL}")

            return True

        except PermissionError as e:
            print(f"{Fore.RED}{EMOJI['ERROR']} 权限错误: {str(e)}{Style.RESET_ALL}")
            print(
                f"{Fore.YELLOW}{EMOJI['INFO']} 请尝试以管理员身份运行此程序{Style.RESET_ALL}"
            )
            return False
        except Exception as e:
            print(f"{Fore.RED}{EMOJI['ERROR']} 重置过程出错: {str(e)}{Style.RESET_ALL}")
            return False

    def _backup_file(self, file_path):
        """备份文件"""
        backup_path = f"{file_path}.bak"
        if os.path.exists(file_path):
            shutil.copy2(file_path, backup_path)
            print(f"{Fore.CYAN}{EMOJI['BACKUP']} 已备份原文件到 {backup_path}{Style.RESET_ALL}")
            return True
        return False

    def _replace_in_file(self, data, pattern, replacement, probe_pattern=None):
        """在文件内容中替换模式"""
        # 确保数据类型一致性
        is_bytes = isinstance(data, bytes)
        
        # 将data转为字符串处理
        if is_bytes:
            data_str = data.decode("utf-8", errors="ignore")
        else:
            data_str = data
            
        # 确保pattern和replacement都是字符串
        if isinstance(pattern, bytes):
            pattern = pattern.decode("utf-8", errors="ignore")
        
        if isinstance(replacement, bytes):
            replacement = replacement.decode("utf-8", errors="ignore")
            
        # 如果提供了probe_pattern，检查是否已经打过补丁
        if probe_pattern:
            if isinstance(probe_pattern, bytes):
                probe_pattern = probe_pattern.decode("utf-8", errors="ignore")
                
            # 检查是否匹配探测模式
            if re.search(probe_pattern, data_str):
                result_str = re.sub(probe_pattern, replacement, data_str)
            else:
                result_str = re.sub(pattern, replacement, data_str)
        else:
            result_str = re.sub(pattern, replacement, data_str)
            
        # 返回与输入相同类型的结果
        if is_bytes:
            return result_str.encode("utf-8")
        else:
            return result_str

    def setup_linux_appimage(self):
        """为Linux系统设置AppImage处理"""
        if sys.platform != "linux":
            return False
            
        # 让用户选择是否输入特定路径
        appimage_input = input(f"{Fore.CYAN}请输入Cursor AppImage路径(留空=自动搜索): {Style.RESET_ALL}")
        
        if appimage_input:
            # 使用用户提供的路径
            self.appimage_path = self._safe_path(appimage_input)
            if not self.appimage_path.exists():
                print(f"{Fore.RED}{EMOJI['ERROR']} 指定的AppImage不存在: {self.appimage_path}{Style.RESET_ALL}")
                return False
        else:
            # 自动查找
            self.appimage_path = self._find_appimage_path()
            if not self.appimage_path:
                print(f"{Fore.RED}{EMOJI['ERROR']} 未找到Cursor AppImage，请手动指定路径{Style.RESET_ALL}")
                return False
                
        # 解包AppImage
        self.appimage_extracted_path = self._extract_appimage(self.appimage_path)
        if not self.appimage_extracted_path:
            return False
            
        # 查找main.js
        self.js_path = self._find_js_in_extracted_appimage(self.appimage_extracted_path)
        if not self.js_path:
            return False
            
        return True

    def patch_main_js(self):
        """修补main.js文件，直接更改机器ID生成方式"""
        # 对于Linux，需要特殊处理
        if sys.platform == "linux" and not self.js_path:
            linux_setup = self.setup_linux_appimage()
            if not linux_setup:
                return False

        if not self.js_path:
            print(f"{Fore.RED}{EMOJI['ERROR']} 未找到main.js文件路径{Style.RESET_ALL}")
            return False

        try:
            print(f"{Fore.CYAN}{EMOJI['INFO']} 正在检查main.js文件...{Style.RESET_ALL}")
            
            # 检查文件是否存在
            if not os.path.exists(self.js_path):
                print(f"{Fore.RED}{EMOJI['ERROR']} main.js文件不存在: {self.js_path}{Style.RESET_ALL}")
                return False
                
            # 读取文件内容
            print(f"{Fore.CYAN}{EMOJI['FILE']} 读取main.js文件...{Style.RESET_ALL}")
            with open(self.js_path, "rb") as f:
                data = f.read()
                
            # 备份原文件（非Linux系统）
            if sys.platform != "linux":
                self._backup_file(self.js_path)
            
            # 生成新的IDs
            machine_id = str(uuid.uuid4())
            mac_address = self.generate_random_mac()
            sqm_id = ""  # Windows SQM ID
            dev_device_id = str(uuid.uuid4())
            
            print(f"{Fore.CYAN}{EMOJI['PATCH']} 正在修补main.js...{Style.RESET_ALL}")
            
            # 检查是否已经打过补丁
            is_patched = any(marker in data.decode("utf-8", errors="ignore") 
                            for marker in ["/*csp1*/", "/*csp2*/", "/*csp3*/", "/*csp4*/"])
            
            if is_patched:
                print(f"{Fore.YELLOW}{EMOJI['INFO']} 检测到main.js已经被修补过，将更新现有的补丁{Style.RESET_ALL}")
            
            # 修补machineId
            data = self._replace_in_file(
                data,
                r"=.{0,50}timeout.{0,10}5e3.*?,",
                f'=/*csp1*/"{machine_id}"/*1csp*/,',
                r"=/\*csp1\*/.*?/\*1csp\*/,"
            )
            
            # 修补MAC地址
            data = self._replace_in_file(
                data,
                r"(function .{0,50}\{).{0,300}Unable to retrieve mac address.*?(\})",
                f'\\1return/*csp2*/"{mac_address}"/*2csp*/;\\2',
                r"()return/\*csp2\*/.*?/\*2csp\*/;()"
            )
            
            # 修补SQM ID
            data = self._replace_in_file(
                data,
                r'return.{0,50}\.GetStringRegKey.*?HKEY_LOCAL_MACHINE.*?MachineId.*?\|\|.*?""',
                f'return/*csp3*/"{sqm_id}"/*3csp*/',
                r"return/\*csp3\*/.*?/\*3csp\*/"
            )
            
            # 修补devDeviceId
            data = self._replace_in_file(
                data,
                r"return.{0,50}vscode\/deviceid.*?getDeviceId\(\)",
                f'return/*csp4*/"{dev_device_id}"/*4csp*/',
                r"return/\*csp4\*/.*?/\*4csp\*/"
            )
            
            # 保存修改后的文件
            print(f"{Fore.CYAN}{EMOJI['FILE']} 保存修改后的main.js...{Style.RESET_ALL}")
            with open(self.js_path, "wb") as f:
                f.write(data)
                
            print(f"{Fore.GREEN}{EMOJI['SUCCESS']} main.js修补成功！{Style.RESET_ALL}")
            print(f"\n{Fore.CYAN}新的机器标识:{Style.RESET_ALL}")
            print(f"{EMOJI['INFO']} machineId: {Fore.GREEN}{machine_id}{Style.RESET_ALL}")
            print(f"{EMOJI['INFO']} MAC Address: {Fore.GREEN}{mac_address}{Style.RESET_ALL}")
            print(f"{EMOJI['INFO']} devDeviceId: {Fore.GREEN}{dev_device_id}{Style.RESET_ALL}")
            
            # 如果是Linux，需要重新打包AppImage
            if sys.platform == "linux" and self.appimage_path and self.appimage_extracted_path:
                print(f"{Fore.CYAN}{EMOJI['INFO']} 由于在Linux系统上，需要重新打包AppImage...{Style.RESET_ALL}")
                if not self._repack_appimage(self.appimage_extracted_path, self.appimage_path):
                    print(f"{Fore.RED}{EMOJI['ERROR']} 重新打包AppImage失败，修改未能完全应用{Style.RESET_ALL}")
                    return False
            
            return True
            
        except PermissionError as e:
            print(f"{Fore.RED}{EMOJI['ERROR']} 权限错误: {str(e)}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}{EMOJI['INFO']} 请尝试以管理员身份运行此程序{Style.RESET_ALL}")
            return False
        except Exception as e:
            print(f"{Fore.RED}{EMOJI['ERROR']} 修补过程出错: {str(e)}{Style.RESET_ALL}")
            print(f"{Fore.RED}{EMOJI['ERROR']} 错误详情: {str(e)}{Style.RESET_ALL}")
            return False
    
    def reset_machine_ids(self):
        """执行最大化重置 - 同时重置storage.json和修补main.js"""
        print(f"\n{Fore.CYAN}{EMOJI['RESET']} 正在执行全面机器标识重置...{Style.RESET_ALL}")
        
        # 重置storage.json
        storage_reset = self.reset_storage_json()
        
        # 修补main.js
        patch_reset = self.patch_main_js()
        
        # 生成结果消息
        if storage_reset and patch_reset:
            result_message = "完全重置成功！配置文件和主程序均已修改"
        elif storage_reset:
            result_message = "部分成功: 配置文件重置成功，但主程序修补失败"
        elif patch_reset:
            result_message = "部分成功: 主程序修补成功，但配置文件重置失败"
        else:
            result_message = "重置失败: 两种方式都未能成功应用，请检查错误信息"
        
        print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.GREEN if (storage_reset or patch_reset) else Fore.RED}{EMOJI['INFO']} {result_message}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        
        return storage_reset or patch_reset


if __name__ == "__main__":
    print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{EMOJI['RESET']} Cursor 机器标识重置工具{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")

    resetter = MachineIDResetter()
    success = resetter.reset_machine_ids()
    
    input(f"{EMOJI['INFO']} 按回车键退出...")