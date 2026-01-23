# core/installer.py
import os
import sys
import subprocess
import platform
import zipfile
import tarfile
import shutil
import urllib.request
import time
import threading
from typing import Optional, Callable

from config import BIN_DIR
from utils import ResourceProvider, is_cmd_available

LogCb = Callable[[str, Optional[str]], None]


def _safe_log(log_cb: LogCb, text: str, tag: Optional[str] = None):
    try:
        log_cb(text, tag)
    except Exception:
        try:
            print(text)
        except Exception:
            pass


def _ensure_bin_dir():
    if not os.path.exists(BIN_DIR):
        os.makedirs(BIN_DIR, exist_ok=True)


class InstallController:
    """
    控制安装线程/下载的控制器，支持 stop() 以中断当前下载/安装动作。
    """
    def __init__(self):
        self._stop_flag = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._current_file = None  # 记录当前下载文件路径（用于在停止时清理）

    def stop(self):
        self._stop_flag.set()

    def should_stop(self) -> bool:
        return self._stop_flag.is_set()

    def set_thread(self, t: threading.Thread):
        self._thread = t

    def is_alive(self) -> bool:
        return self._thread.is_alive() if self._thread else False


class DependencyInstaller:
    def __init__(self, log_callback: LogCb, is_cn_mode: bool = False):
        self.log = log_callback
        self.system = platform.system()
        # 初始化资源提供者，决定下载源
        self.resource = ResourceProvider(is_cn_mode)

    # ---------------------------
    # Public API
    # ---------------------------
    def install_all(self):
        """执行全套安装流程（同步阻塞）"""
        if self.system == "Darwin":
            self._install_mac()
        elif self.system == "Windows":
            self._install_windows()
        else:
            # 对于 Linux，尽量自动检测并提示命令
            self.log("Linux 用户请使用包管理器安装依赖，例如:\n", "info")
            self.log("  Debian/Ubuntu: sudo apt update && sudo apt install -y yt-dlp ffmpeg aria2\n", "tip")
            self.log("  CentOS/Fedora: sudo yum install -y yt-dlp ffmpeg aria2\n", "tip")

    def install_all_threaded(self) -> InstallController:
        """在后台线程运行 install_all，返回 controller（可 stop）"""
        controller = InstallController()

        def worker():
            try:
                _safe_log(self.log, ">>> 后台开始执行依赖修复流程...\n", "info")
                if self.system == "Darwin":
                    self._install_mac()
                elif self.system == "Windows":
                    self._install_windows(controller=controller)
                else:
                    _safe_log(self.log, "Linux 用户请手动使用 apt/yum 安装依赖（已在日志提示）\n", "warning")
            except Exception as e:
                _safe_log(self.log, f"❌ 安装过程中发生异常: {e}\n", "error")

        t = threading.Thread(target=worker, daemon=True)
        controller.set_thread(t)
        t.start()
        return controller

    # ---------------------------
    # Mac installation
    # ---------------------------
    def _install_mac(self):
        """
        macOS: 生成 shell 脚本并用 Terminal 打开（与旧版行为类似）
        """
        _safe_log(self.log, ">>> 正在启动 macOS 终端进行安装...\n", "info")
        _safe_log(self.log, ">>> 请在弹出的终端窗口中输入密码并等待完成。\n", "tip")

        script = """
        echo "=== Universal Downloader Dependency Fixer ==="
        echo "Check Homebrew..."
        if ! command -v brew &> /dev/null; then
            echo "Installing Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi

        echo "Installing yt-dlp ffmpeg aria2..."
        brew install yt-dlp ffmpeg aria2

        echo "=== Done! You can close this window now. ==="
        """
        tmp_script = os.path.join(os.path.expanduser("~"), "ud_install.sh")
        try:
            with open(tmp_script, "w", encoding="utf-8") as f:
                f.write(script)
            os.chmod(tmp_script, 0o755)
            subprocess.run(["open", "-a", "Terminal", tmp_script])
        except Exception as e:
            _safe_log(self.log, f"启动终端失败: {e}\n", "error")

    # ---------------------------
    # Windows installation
    # ---------------------------
    def _install_windows(self, controller: Optional[InstallController] = None):
        """
        Windows 安装流程:
         1) pip 安装/更新 yt-dlp（支持 CN 镜像由 ResourceProvider 控制）
         2) 检查/提示 ffmpeg；若资源提供地址且允许，尝试自动下载并解压到 BIN_DIR
         3) 下载 N_m3u8DL-RE 到 bin 目录
        """
        _safe_log(self.log, ">>> 开始 Windows 环境修复...\n", "info")

        # 1. 安装/更新 yt-dlp via pip
        pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp", "--no-warn-script-location"]
        if getattr(self.resource, "is_cn", False):
            _safe_log(self.log, ">>> 检测到 CN 模式，使用清华源加速 pip...\n", "info")
            pip_cmd.extend(["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"])
        try:
            _safe_log(self.log, ">>> 正在安装/更新 yt-dlp...\n", "info")
            subprocess.check_call(pip_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _safe_log(self.log, "✅ yt-dlp 安装/更新成功\n", "success")
        except subprocess.CalledProcessError:
            _safe_log(self.log, "❌ yt-dlp 安装/更新失败，请检查 Python 环境或手动安装 yt-dlp。\n", "error")

        # 2. ffmpeg 检查与可选自动下载（自动下载可能很大，视资源提供情况而定）
        if not is_cmd_available("ffmpeg"):
            _safe_log(self.log, "⚠️ 未检测到 FFmpeg。\n", "warning")
            ff_url = self.resource.get_dependency_url("ffmpeg")
            if ff_url:
                _safe_log(self.log, f">>> 检测到可用 FFmpeg 下载来源，准备下载到 {BIN_DIR}（文件较大）...\n", "info")
                try:
                    _ensure_bin_dir()
                    dest = os.path.join(BIN_DIR, os.path.basename(ff_url.split("?")[0]))
                    ok = self._download_file(ff_url, dest, controller=controller, desc="FFmpeg")
                    if ok:
                        # 试解压并查找 ffmpeg 可执行
                        installed = self._extract_archive_to_bin(dest)
                        if installed:
                            _safe_log(self.log, "✅ FFmpeg 已成功安装到 bin 目录（或已解压）。\n", "success")
                        else:
                            _safe_log(self.log, "⚠️ FFmpeg 下载完成但未能自动安装，请手动将 ffmpeg 可执行加入 PATH 或放到 bin 目录。\n", "warning")
                        try:
                            os.remove(dest)
                        except Exception:
                            pass
                    else:
                        _safe_log(self.log, "❌ FFmpeg 下载或安装被中止/失败。\n", "error")
                except Exception as e:
                    _safe_log(self.log, f"❌ FFmpeg 自动安装失败: {e}\n", "error")
            else:
                _safe_log(self.log, "提示：请从 FFmpeg 官网下载并将 ffmpeg.exe 放入 bin 目录或 PATH。\n", "info")
        else:
            _safe_log(self.log, "✅ 已检测到系统 FFmpeg。\n", "success")

        # 3. N_m3u8DL-RE
        self._install_local_re(controller=controller)

    # ---------------------------
    # RE 安装
    # ---------------------------
    def _install_local_re(self, controller: Optional[InstallController] = None):
        """下载 N_m3u8DL-RE 到本地 bin 目录（同步）"""
        target_name = "N_m3u8DL-RE.exe" if self.system == "Windows" else "N_m3u8DL-RE"
        target_path = os.path.join(BIN_DIR, target_name)

        if os.path.exists(target_path):
            _safe_log(self.log, f"✅ N_m3u8DL-RE 已存在 ({target_path})\n", "success")
            return True

        # 获取下载链接
        url = self.resource.get_dependency_url("N_m3u8DL-RE")
        if not url:
            _safe_log(self.log, "❌ 无法获取 RE 下载链接\n", "error")
            return False

        _ensure_bin_dir()
        _safe_log(self.log, f">>> 正在下载 N_m3u8DL-RE...\nURL: {url}\n", "info")
        tmp_name = os.path.join(BIN_DIR, "re_temp.bin")
        try:
            ok = self._download_file(url, tmp_name, controller=controller, desc="N_m3u8DL-RE")
            if not ok:
                _safe_log(self.log, "❌ RE 下载被中止或失败。\n", "error")
                try:
                    os.remove(tmp_name)
                except Exception:
                    pass
                return False

            # 可能是 zip/tar 包，尝试解压（若不是压缩包则直接移动作为可执行）
            installed = self._extract_archive_to_bin(tmp_name, expected_name="N_m3u8DL-RE")
            if installed:
                try:
                    os.remove(tmp_name)
                except Exception:
                    pass
                _safe_log(self.log, f"✅ N_m3u8DL-RE 安装成功到 {BIN_DIR}\n", "success")
                return True
            else:
                # 直接移动并设置可执行
                try:
                    os.replace(tmp_name, target_path)
                    if self.system != "Windows":
                        os.chmod(target_path, 0o755)
                    _safe_log(self.log, f"✅ N_m3u8DL-RE 已放置到 {target_path}\n", "success")
                    return True
                except Exception as e:
                    _safe_log(self.log, f"❌ 无法将下载文件移动到 bin: {e}\n", "error")
                    return False
        except Exception as e:
            _safe_log(self.log, f"❌ 下载/安装 RE 失败: {e}\n", "error")
            try:
                os.remove(tmp_name)
            except Exception:
                pass
            return False

    def install_local_re_threaded(self) -> InstallController:
        """在后台线程下载并安装 RE，返回 controller"""
        controller = InstallController()

        def worker():
            try:
                self._install_local_re(controller=controller)
            except Exception as e:
                _safe_log(self.log, f"❌ 安装过程中发生异常: {e}\n", "error")

        t = threading.Thread(target=worker, daemon=True)
        controller.set_thread(t)
        t.start()
        return controller

    # ---------------------------
    # Helpers: download, extract
    # ---------------------------
    def _download_file(self, url: str, dest_path: str, controller: Optional[InstallController] = None,
                       desc: Optional[str] = None, retries: int = 3, timeout: int = 30) -> bool:
        """
        分块下载，显示进度；支持中断（controller.should_stop())；返回 True/False。
        使用 urllib for stdlib-only 环境，适配大多数 URL（包含 github release zip）
        """
        desc = desc or "file"
        attempt = 0
        while attempt < retries:
            if controller and controller.should_stop():
                _safe_log(self.log, f"⚠️ {desc} 下载已被取消。\n", "warning")
                return False
            attempt += 1
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ud-installer/1.0"})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    total = resp.getheader("Content-Length")
                    total = int(total) if total and total.isdigit() else None
                    downloaded = 0
                    chunk_size = 32 * 1024
                    start = time.time()
                    tmp_path = dest_path + ".part"
                    # ensure dir
                    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
                    controller and setattr(controller, "_current_file", tmp_path)
                    with open(tmp_path, "wb") as f:
                        while True:
                            if controller and controller.should_stop():
                                _safe_log(self.log, f"⚠️ {desc} 下载被用户取消。\n", "warning")
                                return False
                            chunk = resp.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            # 频率限制：每 0.2 秒输出一次进度
                            if total:
                                percent = downloaded * 100 / total
                                elapsed = time.time() - start
                                speed = downloaded / 1024 / max(elapsed, 0.1)
                                _safe_log(self.log, f"\r{desc} 下载: {percent:.1f}% ({downloaded//1024} KB) 速度: {speed:.1f} KB/s", "info")
                            else:
                                _safe_log(self.log, f"\r{desc} 下载: {downloaded//1024} KB", "info")
                    # 重命名
                    try:
                        os.replace(tmp_path, dest_path)
                    except Exception:
                        # fallback copy+remove
                        shutil.copyfile(tmp_path, dest_path)
                        os.remove(tmp_path)
                    _safe_log(self.log, f"\n>>> {desc} 下载完成: {dest_path}\n", "info")
                    return True
            except Exception as e:
                _safe_log(self.log, f"\n⚠️ {desc} 下载失败（尝试 {attempt}/{retries}）: {e}\n", "warning")
                time.sleep(1 + attempt)
        _safe_log(self.log, f"❌ {desc} 下载多次重试失败。\n", "error")
        return False

    def _extract_archive_to_bin(self, archive_path: str, expected_name: Optional[str] = None) -> bool:
        """
        尝试识别并解压 zip/tar* 到 BIN_DIR，并尝试找到可执行（或指定的 expected_name）。
        返回 True 如果解压并放置了可执行文件（或找到了 expected_name），否则 False。
        """
        try:
            if zipfile.is_zipfile(archive_path):
                with zipfile.ZipFile(archive_path, "r") as z:
                    namelist = z.namelist()
                    # 尝试找到常见 exe 或二进制
                    candidates = [n for n in namelist if (n.endswith(".exe") or not os.path.splitext(n)[1])]
                    # 优先查找 expected_name
                    if expected_name:
                        for n in namelist:
                            if os.path.basename(n).startswith(expected_name):
                                target = n
                                break
                        else:
                            target = candidates[0] if candidates else None
                    else:
                        target = candidates[0] if candidates else None
                    if not target:
                        # 直接解压全部到 BIN_DIR
                        z.extractall(BIN_DIR)
                        return True
                    else:
                        extracted = z.read(target)
                        out_path = os.path.join(BIN_DIR, os.path.basename(target))
                        with open(out_path, "wb") as f:
                            f.write(extracted)
                        if platform.system() != "Windows":
                            os.chmod(out_path, 0o755)
                        return True
            # tar archives
            if tarfile.is_tarfile(archive_path):
                with tarfile.open(archive_path, "r:*") as tar:  # type: ignore
                    members = tar.getmembers()
                    candidates = [m.name for m in members if (m.name.endswith(".exe") or os.path.basename(m.name) == expected_name or not os.path.splitext(m.name)[1])]
                    if candidates:
                        # 提取所有到 bin，然后确保权限
                        tar.extractall(BIN_DIR)
                        for c in candidates:
                            try:
                                p = os.path.join(BIN_DIR, os.path.basename(c))
                                if platform.system() != "Windows":
                                    os.chmod(p, 0o755)
                            except Exception:
                                pass
                        return True
                    else:
                        tar.extractall(BIN_DIR)
                        return True
        except Exception as e:
            _safe_log(self.log, f"❌ 解压失败: {e}\n", "error")
            return False
        return False

    # ---------------------------
    # Status check
    # ---------------------------
    def check_status(self) -> dict:
        """返回当前依赖状态字典，用于 UI 显示红/绿灯"""
        status = {
            "yt-dlp": is_cmd_available("yt-dlp"),
            "ffmpeg": is_cmd_available("ffmpeg"),
            "re": False,
            "bin_dir": BIN_DIR
        }

        re_exe = "N_m3u8DL-RE.exe" if self.system == "Windows" else "N_m3u8DL-RE"
        if os.path.exists(os.path.join(BIN_DIR, re_exe)) or is_cmd_available("N_m3u8DL-RE"):
            status["re"] = True

        return status
