# core/installer.py
import os
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import zipfile
from typing import Optional, Callable

from config import BIN_DIR
from config.config import SYSTEM, IS_MAC, IS_WIN, IS_LINUX
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

# Raw log helper: logs plain text, bypassing i18n templates
def _log_raw(log_cb: LogCb, text: str, tag: Optional[str] = None):
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
    def __init__(self, log_callback: LogCb, translations: Optional[dict] = None, lang: str = "en", is_cn_mode: bool = False):
        self.log = log_callback
        self.translations = translations or {}
        self.lang = lang
        self.system = SYSTEM
        # 初始化资源提供者，决定下载源
        self.resource = ResourceProvider(is_cn_mode)

    # -------- i18n helpers --------
    def set_language(self, lang: str):
        if lang:
            self.lang = lang

    def _t(self, key: str, default: str = "", **kwargs) -> str:
        try:
            table = self.translations.get(self.lang) or {}
            text = table.get(key, default)
            if kwargs:
                return text.format(**kwargs)
            return text
        except Exception:
            return default

    # ---------------------------
    # Public API
    # ---------------------------
    def install_all(self):
        """Install/update all dependencies into BIN_DIR (no system package managers)."""
        ok = True
        try:
            ok &= bool(self._ensure_yt_dlp())
        except Exception as e:
            _log_raw(self.log, f"yt-dlp installation failed: {e}\n", "warning")
            ok = False
        try:
            ok &= bool(self._ensure_ffmpeg())
        except Exception as e:
            _log_raw(self.log, f"ffmpeg installation failed: {e}\n", "warning")
            ok = False
        try:
            ok &= bool(self._ensure_aria2())
        except Exception as e:
            _log_raw(self.log, f"aria2 installation failed: {e}\n", "warning")
            ok = False
        try:
            ok &= bool(self._ensure_re())
        except Exception as e:
            _log_raw(self.log, f"N_m3u8DL-RE installation failed: {e}\n", "warning")
            ok = False
        return ok

    def install_all_threaded(self) -> InstallController:
        controller = InstallController()

        def worker():
            _log_raw(self.log, ">>> Installing dependencies to local bin directory...\n", "info")

            ok = True
            try:
                ok &= bool(self._ensure_yt_dlp(controller))
                ok &= bool(self._ensure_ffmpeg(controller))
                ok &= bool(self._ensure_aria2(controller))
                ok &= bool(self._ensure_re(controller))
            except Exception as e:
                ok = False
                _log_raw(self.log, f"Installer crashed: {e}\n", "error")

            if ok:
                _log_raw(self.log, "All dependencies are ready.\n", "success")
            else:
                _log_raw(self.log, "Some dependencies failed to install. Check logs above.\n", "warning")

        t = threading.Thread(target=worker, daemon=True)
        controller.set_thread(t)
        t.start()
        return controller

    # ---------------------------
    # Unified ensure helpers (bin-based, cross-platform)
    # ---------------------------
    def _ensure_yt_dlp(self, controller: Optional[InstallController] = None) -> bool:
        name = "yt-dlp.exe" if IS_WIN else "yt-dlp"
        target = os.path.join(BIN_DIR, name)

        if os.path.exists(target):
            _log_raw(self.log, f"yt-dlp found in bin: {target}\n", "success")
            return True

        url = self.resource.get_dependency_url("yt-dlp")
        if not url:
            _log_raw(self.log, "yt-dlp download URL not available.\n", "warning")
            return False

        _ensure_bin_dir()
        _log_raw(self.log, f">>> Downloading yt-dlp...\nURL: {url}\n", "info")
        ok = self._download_file(url, target, controller=controller, desc="yt-dlp")
        if not ok:
            _log_raw(self.log, "yt-dlp download failed.\n", "warning")
            return False

        if not IS_WIN:
            try:
                os.chmod(target, 0o755)
            except Exception as e:
                _log_raw(self.log, f"Failed to set executable permission on yt-dlp: {e}\n", "warning")
        return True

    def _ensure_ffmpeg(self, controller: Optional[InstallController] = None) -> bool:
        name = "ffmpeg.exe" if IS_WIN else "ffmpeg"
        target = os.path.join(BIN_DIR, name)

        if os.path.exists(target):
            _log_raw(self.log, f"ffmpeg found in bin: {target}\n", "success")
            return True

        url = self.resource.get_dependency_url("ffmpeg")
        if not url:
            _log_raw(self.log, "ffmpeg download URL not available.\n", "warning")
            return False

        _ensure_bin_dir()
        _log_raw(self.log, f">>> Downloading ffmpeg...\nURL: {url}\n", "info")
        tmp = os.path.join(BIN_DIR, "ffmpeg.tmp")
        ok = self._download_file(url, tmp, controller=controller, desc="ffmpeg")
        if not ok:
            _log_raw(self.log, "ffmpeg download failed.\n", "warning")
            try:
                os.remove(tmp)
            except Exception:
                pass
            return False

        installed = False
        # ffmpeg-static on macOS provides a raw executable, not an archive
        if IS_MAC and not (zipfile.is_zipfile(tmp) or tarfile.is_tarfile(tmp)):
            try:
                shutil.move(tmp, target)
                if not IS_WIN:
                    os.chmod(target, 0o755)
                installed = True
            except Exception as e:
                _log_raw(self.log, f"Failed to place ffmpeg binary: {e}\n", "warning")
                installed = False
        else:
            # Windows ffmpeg ZIP: explicitly extract ffmpeg.exe
            if IS_WIN and zipfile.is_zipfile(tmp):
                try:
                    with zipfile.ZipFile(tmp, 'r') as z:
                        exe_member = None
                        for n in z.namelist():
                            if n.lower().endswith('ffmpeg.exe'):
                                exe_member = n
                                break
                        if not exe_member:
                            raise RuntimeError('ffmpeg.exe not found in ZIP')
                        out_path = os.path.join(BIN_DIR, 'ffmpeg.exe')
                        with open(out_path, 'wb') as f:
                            f.write(z.read(exe_member))
                    installed = True
                except Exception as e:
                    _log_raw(self.log, f"Failed to extract ffmpeg.exe: {e}\n", "warning")
                    installed = False
            else:
                installed = self._extract_archive_to_bin(tmp, expected_name="ffmpeg")
                if installed:
                    installed = self._finalize_ffmpeg_binary()

        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

        if not installed:
            _log_raw(self.log, "ffmpeg installation failed.\n", "warning")
            return False
        return True

    def _ensure_re(self, controller: Optional[InstallController] = None) -> bool:
        """下载 N_m3u8DL-RE 到本地 bin 目录（同步）"""
        target_name = "N_m3u8DL-RE.exe" if IS_WIN else "N_m3u8DL-RE"
        target_path = os.path.join(BIN_DIR, target_name)

        if os.path.exists(target_path):
            _log_raw(self.log, f"N_m3u8DL-RE already exists ({target_path}).\n", "success")
            return True

        # Get download link
        url = self.resource.get_dependency_url("N_m3u8DL-RE")
        if not url:
            _log_raw(self.log, "Failed to obtain N_m3u8DL-RE download URL.\n", "warning")
            return False

        _ensure_bin_dir()
        _log_raw(self.log, f">>> Downloading N_m3u8DL-RE...\nURL: {url}\n", "info")
        tmp_name = os.path.join(BIN_DIR, "re_temp.bin")
        try:
            ok = self._download_file(url, tmp_name, controller=controller, desc="N_m3u8DL-RE")
            if not ok:
                _log_raw(self.log, "N_m3u8DL-RE download was cancelled or failed.\n", "warning")
                try:
                    os.remove(tmp_name)
                except Exception:
                    pass
                return False

            # Might be zip/tar, try to extract (otherwise move as executable)
            installed = self._extract_archive_to_bin(tmp_name, expected_name="N_m3u8DL-RE")
            if installed:
                try:
                    os.remove(tmp_name)
                except Exception:
                    pass
                _log_raw(self.log, f"N_m3u8DL-RE successfully installed to {BIN_DIR}.\n", "success")
                return True
            else:
                # Directly move and set executable
                try:
                    os.replace(tmp_name, target_path)
                    if not IS_WIN:
                        os.chmod(target_path, 0o755)
                    _log_raw(self.log, f"N_m3u8DL-RE placed at {target_path}.\n", "success")
                    return True
                except Exception as e:
                    _log_raw(self.log, f"Failed to move downloaded file to bin: {e}\n", "warning")
                    return False
        except Exception as e:
            _log_raw(self.log, f"Failed to download/install N_m3u8DL-RE: {e}\n", "warning")
            try:
                os.remove(tmp_name)
            except Exception:
                pass
            return False



    # ---------------------------
    # Helpers: download, extract
    # ---------------------------
    def _extract_archive_to_bin(self, archive_path: str, expected_name: Optional[str] = None) -> bool:
        """
        Try to extract zip/tar archives into BIN_DIR and place the executable.
        Returns True if something usable was extracted.
        """
        try:
            # ZIP archives
            if zipfile.is_zipfile(archive_path):
                with zipfile.ZipFile(archive_path, "r") as z:
                    names = z.namelist()
                    target = None
                    if expected_name:
                        for n in names:
                            if os.path.basename(n).startswith(expected_name):
                                target = n
                                break
                    if not target:
                        # pick first executable-like file
                        for n in names:
                            base = os.path.basename(n)
                            if IS_WIN and base.lower().endswith('.exe'):
                                target = n
                                break
                            if not IS_WIN and base and not os.path.splitext(base)[1]:
                                target = n
                                break
                    if target:
                        out_path = os.path.join(BIN_DIR, os.path.basename(target))
                        with open(out_path, 'wb') as f:
                            f.write(z.read(target))
                        if not IS_WIN:
                            os.chmod(out_path, 0o755)
                        return True
                    # fallback: extract all
                    z.extractall(BIN_DIR)
                    return True

            # TAR archives
            if tarfile.is_tarfile(archive_path):
                with tarfile.open(archive_path, 'r:*') as tar:
                    members = tar.getmembers()
                    candidates = []
                    for m in members:
                        base = os.path.basename(m.name)
                        if expected_name and base.startswith(expected_name):
                            candidates.append(m)
                        elif IS_WIN and base.lower().endswith('.exe'):
                            candidates.append(m)
                        elif not IS_WIN and base and not os.path.splitext(base)[1]:
                            candidates.append(m)
                    if candidates:
                        tar.extractall(BIN_DIR)
                        for m in candidates:
                            try:
                                p = os.path.join(BIN_DIR, os.path.basename(m.name))
                                if not IS_WIN:
                                    os.chmod(p, 0o755)
                            except Exception:
                                pass
                        return True
                    tar.extractall(BIN_DIR)
                    return True
        except Exception as e:
            _log_raw(self.log, f"Extraction failed: {e}\n", "warning")
            return False
        return False

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
                _log_raw(self.log, f"{desc} download was cancelled.\n", "warning")
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
                                _log_raw(self.log, f"{desc} download cancelled by user.\n", "warning")
                                return False
                            chunk = resp.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            # Throttle: print progress every 0.5s
                            if total:
                                percent = downloaded * 100 / total
                                elapsed = time.time() - start
                                speed = downloaded / 1024 / max(elapsed, 0.1)
                                now = time.time()
                                if not hasattr(self, "_last_progress_log") or now - getattr(self, "_last_progress_log") > 0.5:
                                    self._last_progress_log = now
                                    _log_raw(
                                        self.log,
                                        f"\r{desc} Download: {percent:.1f}% ({downloaded // 1024} KB) Speed: {speed:.1f} KB/s",
                                        "info",
                                    )
                            else:
                                _log_raw(self.log, f"\r{desc} Download: {downloaded // 1024} KB", "info")
                    # Rename
                    try:
                        os.replace(tmp_path, dest_path)
                    except Exception:
                        # fallback copy+remove
                        shutil.copyfile(tmp_path, dest_path)
                        os.remove(tmp_path)
                    _log_raw(self.log, f"\n>>> {desc} download completed: {dest_path}\n", "info")
                    return True
            except Exception as e:
                _log_raw(self.log, f"\n{desc} download failed (attempt {attempt}/{retries}): {e}\n", "warning")
                time.sleep(1 + attempt)
        _log_raw(self.log, f"{desc} download failed after multiple retries.\n", "warning")
        return False

        # (EXTRACTION MOVED TO _extract_archive_to_bin)
    def _ensure_aria2(self, controller: Optional[InstallController] = None) -> bool:
        name = "aria2c.exe" if IS_WIN else "aria2c"
        target = os.path.join(BIN_DIR, name)

        if os.path.exists(target):
            _log_raw(self.log, f"aria2 found in bin: {target}\n", "success")
            return True

        url = self.resource.get_dependency_url("aria2")
        if not url:
            _log_raw(self.log, "aria2 download URL not available.\n", "warning")
            return False

        _ensure_bin_dir()
        _log_raw(self.log, f">>> Downloading aria2...\nURL: {url}\n", "info")
        tmp = os.path.join(BIN_DIR, "aria2.tmp")
        ok = self._download_file(url, tmp, controller=controller, desc="aria2")
        if not ok:
            _log_raw(self.log, "aria2 download failed.\n", "warning")
            try:
                os.remove(tmp)
            except Exception:
                pass
            return False

        installed = self._extract_archive_to_bin(tmp, expected_name="aria2")
        try:
            os.remove(tmp)
        except Exception:
            pass
        if not installed:
            _log_raw(self.log, "aria2 extraction failed.\n", "warning")
            return False
        return True

    # ---------------------------
    # Status check
    # ---------------------------
    def check_status(self) -> dict:
        return {
            "yt-dlp": os.path.exists(os.path.join(BIN_DIR, "yt-dlp.exe" if IS_WIN else "yt-dlp")),
            "ffmpeg": os.path.exists(os.path.join(BIN_DIR, "ffmpeg.exe" if IS_WIN else "ffmpeg")),
            "aria2": os.path.exists(os.path.join(BIN_DIR, "aria2c.exe" if IS_WIN else "aria2c")),
            "re": os.path.exists(os.path.join(BIN_DIR, "N_m3u8DL-RE.exe" if IS_WIN else "N_m3u8DL-RE")),
            "bin_dir": BIN_DIR,
        }

    def _finalize_ffmpeg_binary(self) -> bool:
        exe_name = "ffmpeg.exe" if IS_WIN else "ffmpeg"
        target = os.path.join(BIN_DIR, exe_name)

        # Find ffmpeg executable anywhere under BIN_DIR
        found = None
        for root, dirs, files in os.walk(BIN_DIR):
            if exe_name in files:
                found = os.path.join(root, exe_name)
                break

        if not found:
            return False

        try:
            shutil.copy2(found, target)
            if not IS_WIN:
                os.chmod(target, 0o755)
        except Exception as e:
            _log_raw(self.log, f"Failed to finalize ffmpeg binary: {e}\n", "warning")
            return False

        # Remove EVERYTHING except the single ffmpeg binary
        for entry in os.listdir(BIN_DIR):
            p = os.path.join(BIN_DIR, entry)
            if p == target:
                continue
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p)
                elif os.path.isfile(p) and entry not in {
                    exe_name,
                    "yt-dlp.exe" if IS_WIN else "yt-dlp",
                    "aria2c.exe" if IS_WIN else "aria2c",
                    "N_m3u8DL-RE.exe" if IS_WIN else "N_m3u8DL-RE",
                }:
                    os.remove(p)
            except Exception:
                pass

        return True