# core/downloader.py
import os
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional, Tuple

from config import BIN_DIR
from config.config import SYSTEM, IS_WIN, COOKIE_PERSISTENT_CACHE_ENABLED
from utils import parse_cookie_file, is_cmd_available

LogCb = Callable[[str, Optional[str]], None]


def _safe_log(log_cb: LogCb, text: str, tag: Optional[str] = None):
    try:
        log_cb(text, tag)
    except Exception:
        # 日志回调不可用时，降级到 print（避免抛出）
        try:
            print(text)
        except Exception:
            pass


def _mask_cmd_for_display(cmd_list):
    """
    返回一串用于显示的命令字符串，脱敏 Cookie header 等敏感信息。
    """
    out = []
    for part in cmd_list:
        if isinstance(part, str) and "Cookie:" in part:
            out.append("Cookie: ***")
        else:
            # 简单 quote 显示，不用于执行
            if " " in str(part) or '"' in str(part):
                out.append(f'"{str(part)}"')
            else:
                out.append(str(part))
    return " ".join(out)


def _is_twitter_url(url: str) -> bool:
    return "twitter.com" in url or "x.com" in url


class DownloadController:
    """
    控制器用于在 UI 或上层持有正在运行的进程引用，支持 stop()
    """

    def __init__(self):
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def _set_proc(self, proc: subprocess.Popen):
        with self._lock:
            self._proc = proc

    def _set_thread(self, thread: threading.Thread):
        with self._lock:
            self._thread = thread

    def stop(self):
        with self._lock:
            proc = self._proc
        if not proc:
            return
        try:
            if IS_WIN:
                # Force kill process tree on Windows
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                try:
                    proc.terminate()
                except Exception:
                    proc.kill()
        except Exception:
            # 忽略任何停止时的异常
            pass


class DownloaderEngine:
    def __init__(self, log_callback: LogCb, translations: Optional[dict] = None, lang: str = "en", on_done=None):
        """
        :param log_callback: function (text, tag) -> None, used to send logs back to UI
        :param translations: translations dict loaded from json (e.g. {"zh": {...}, "en": {...}})
        :param lang: current language key, default 'zh'
        """
        self.log = log_callback
        self.translations = translations or {}
        self.lang = lang
        self.on_done = on_done
        self.process: Optional[subprocess.Popen] = None
        self.system = SYSTEM

        # Windows: hide console window (keep legacy behavior)
        self.startupinfo = None
        if IS_WIN:
            try:
                self.startupinfo = subprocess.STARTUPINFO()
                self.startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            except Exception:
                self.startupinfo = None

    def _bootstrap_cookies_from_browser(self, browser: str, target_url: str) -> Optional[str]:
        """Extract browser cookies into a cookies.txt file using yt-dlp (first-run bootstrap)."""
        try:
            from config.config import USER_CONFIG_DIR
            base = Path(USER_CONFIG_DIR)
            base.mkdir(parents=True, exist_ok=True)
            out_file = base / f"cookies_{browser}.txt"

            cmd = [
                "yt-dlp",
                "--cookies-from-browser", browser,
                "--skip-download",
                "--print-to-file", "cookies", str(out_file),
                target_url,
            ]

            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

            if out_file.exists() and out_file.stat().st_size > 0:
                _safe_log(self.log, f">>> 🍪 Extracted cookies from {browser} cache\n", "success")
                return str(out_file)
        except Exception:
            pass
        return None

    def _notify_done(self, success: bool, rc: Optional[int]):
        """Notify completion (UI is responsible for idempotency)."""
        cb = self.on_done
        if cb:
            try:
                cb(success, rc)
            except Exception:
                pass

    # -------- i18n helpers (UI-facing logs only) --------
    def set_language(self, lang: str):
        """Update current language (called by UI when language changes)."""
        if lang:
            self.lang = lang

    def _t(self, key: str, default: str = "", **kwargs) -> str:
        """Translate a message key using current language.
        Only intended for user-facing / interactive logs.
        """
        try:
            table = self.translations.get(self.lang) or {}
            text = table.get(key, default)
            if kwargs:
                return text.format(**kwargs)
            return text
        except Exception:
            return default

    def _check_common_tools(self, engine: str):
        """
        检查常用外部命令是否可用，并在日志中给出提示（但不强制失败）。
        """
        # 检查 yt-dlp
        if engine in ("native", "aria2"):
            if not is_cmd_available("yt-dlp"):
                _safe_log(self.log, self._t('log_check_yt_fail',
                                            ">>> ❌ Env Check (System): yt-dlp not found. Click [Fix Dependencies].\n"),
                          "warning")
        if engine == "re":
            re_exe = "N_m3u8DL-RE.exe" if self.system == "Windows" else "N_m3u8DL-RE"
            re_path = os.path.join(BIN_DIR, re_exe)
            if not os.path.exists(re_path) and not is_cmd_available("N_m3u8DL-RE"):
                _safe_log(self.log, self._t('log_re_not_found', "❌ Error: N_m3u8DL-RE not found in 'bin' folder!"),
                          "error")
        if engine == "aria2":
            if not is_cmd_available("aria2c"):
                _safe_log(self.log, self._t('log_tip_install', "Tip: Please check if yt-dlp/ffmpeg is installed."),
                          "warning")

    def _build_command(self, url: str, engine: str, save_dir: str,
                       cookie_src: str, cookie_path: str, threads: int) -> Tuple[list, Optional[str]]:
        """
        构建要执行的命令列表，并返回 (cmd_list, maybe_cookie_header_str)
        如果需要向 RE 注入 header，则 cookie_header_str 为 "Cookie: k=v; k2=v2" 格式，否则为 None。
        """
        cmd = []
        cookie_header = None

        def _is_stream_url(u: str) -> bool:
            ul = u.lower()
            return ul.endswith('.m3u8') or ul.endswith('.mpd') or 'm3u8' in ul

        # First-run bootstrap: always try browser cookies if no cookie file exists
        if not cookie_path:
            # choose a reasonable browser source
            bootstrap_browser = cookie_src if cookie_src in ["chrome", "edge", "firefox", "safari"] else "chrome"
            cookie_path = self._bootstrap_cookies_from_browser(bootstrap_browser, url)

        if engine == "re":
            # N_m3u8DL-RE
            # RE only supports stream URLs
            if not _is_stream_url(url):
                raise ValueError("RE engine only supports stream URLs (m3u8/mpd). Use yt-dlp for webpage URLs.")
            re_exe = "N_m3u8DL-RE.exe" if self.system == "Windows" else "N_m3u8DL-RE"
            re_path = os.path.join(BIN_DIR, re_exe)
            exe_cmd = re_path if os.path.isfile(re_path) else "N_m3u8DL-RE"

            cmd = [
                exe_cmd,
                url,
                "--save-dir", save_dir,
                "--auto-select",
                "--no-log"  # 禁用 RE 自己的日志文件，直接读 stdout
            ]

            # Only override thread count if user explicitly set it
            if threads > 0:
                cmd.extend(["--thread-count", str(threads)])

            # Prefer cached cookies.txt (fast path), regardless of UI cookie mode
            cookie_str = None
            if COOKIE_PERSISTENT_CACHE_ENABLED and cookie_path:
                try:
                    cookie_str = parse_cookie_file(cookie_path, url)
                except Exception:
                    cookie_str = None

            # If cached/matched cookies exist, inject as header and skip browser cookies
            if cookie_str:
                cookie_header = f"Cookie: {cookie_str}"
                cmd.extend(["--header", cookie_header])
                _safe_log(self.log, self._t('log_cookie_match', ">>> ✅ Using cached cookies.txt\n"), "success")
            else:
                # Fallback to UI-selected cookie mode
                if cookie_src == "file" and cookie_path:
                    _safe_log(self.log,
                              self._t('log_cookie_filter', ">>> Filtering cookies for target host: {host}...\n",
                                      host=""), "info")
                    try:
                        cookie_str = parse_cookie_file(cookie_path, url)
                    except Exception as e:
                        _safe_log(self.log,
                                  self._t('log_cookie_parse_error', ">>> ⚠️ Failed to parse cookie file: {e}\n", e=e),
                                  "warning")
                    if cookie_str:
                        cookie_header = f"Cookie: {cookie_str}"
                        cmd.extend(["--header", cookie_header])
                        _safe_log(self.log, self._t('log_cookie_match', ">>> ✅ Loaded cookies from file\n"), "success")
                    else:
                        _safe_log(self.log, self._t('log_cookie_none',
                                                    "⚠️ No cookies found for {host}. Falling back to direct download.",
                                                    host=""), "warning")
                elif cookie_src in ["chrome", "edge", "safari", "firefox"]:
                    _safe_log(self.log,
                              self._t('log_re_no_browser', "⚠️ RE engine does not support direct browser link."),
                              "warning")

        else:
            # yt-dlp 路径
            yt_path = os.path.join(BIN_DIR, "yt-dlp.exe" if IS_WIN else "yt-dlp")
            yt_cmd = yt_path if os.path.isfile(yt_path) else "yt-dlp"

            cmd = [
                yt_cmd,
                "-P", save_dir,
                "--merge-output-format", "mp4",
                "--retries", "10",
                "-f", "bv+ba/b",
                url
            ]

            if engine == "aria2":
                aria2_path = os.path.join(BIN_DIR, "aria2c.exe" if IS_WIN else "aria2c")
                aria2_cmd = aria2_path if os.path.isfile(aria2_path) else "aria2c"

                cmd.extend([
                    "--downloader", aria2_cmd,
                    "--downloader-args", f"{aria2_cmd}:-x {threads} -k 1M"
                ])
                _safe_log(self.log,
                          self._t('log_aria2_enabled', ">>> Aria2 acceleration enabled (threads: {threads})\n",
                                  threads=threads), "info")

            # yt-dlp extractor-aware cookie strategy
            if _is_twitter_url(url):
                # Twitter / X: always prefer browser cookies (officially supported)
                if cookie_src in ["chrome", "edge", "firefox", "safari"]:
                    _safe_log(self.log,
                              self._t('log_cookie_from_browser', ">>> Using browser cookies for Twitter/X: {browser}\n",
                                      browser=cookie_src), "info")
                    cmd.extend(["--cookies-from-browser", cookie_src])
                else:
                    _safe_log(self.log, self._t('log_cookie_none',
                                                "⚠️ Twitter/X requires browser cookies for authenticated access."),
                              "warning")
            else:
                # Non-Twitter sites: prefer cookies.txt (fast path)
                cookie_str = None
                if cookie_path:
                    try:
                        cookie_str = parse_cookie_file(cookie_path, url)
                    except Exception:
                        cookie_str = None

                if cookie_str:
                    _safe_log(self.log, self._t('log_cookie_match', ">>> ✅ Using cookies.txt (auto)\n"), "success")
                    cmd.extend(["--add-header", f"Cookie: {cookie_str}"])
                else:
                    # Fallback to browser cookies
                    if cookie_src in ["chrome", "edge", "firefox", "safari"]:
                        _safe_log(self.log,
                                  self._t('log_cookie_from_browser', ">>> Loading cookies from browser: {browser}\n",
                                          browser=cookie_src), "info")
                        cmd.extend(["--cookies-from-browser", cookie_src])

        return cmd, cookie_header

    def run(self, url: str, options: dict, controller: Optional['DownloadController'] = None) -> Tuple[
        bool, Optional[int]]:
        """
        同步运行下载（阻塞）。保持与旧版接口一致：返回 True/False。
        options: 包含 engine, threads, cookie_source, cookie_path, download_dir
        """
        engine = options.get("engine", "native")
        save_dir = options.get("download_dir", ".")
        cookie_src = options.get("cookie_source", "none")
        cookie_path = options.get("cookie_path", "")
        # 保证 threads 为 int
        try:
            threads = int(options.get("threads", 0))
        except Exception:
            threads = 0

        # 工具检查提示（不会直接抛错）
        self._check_common_tools(engine)

        # 构建命令
        cmd, cookie_header = self._build_command(url, engine, save_dir, cookie_src, cookie_path, threads)

        # 脱敏后的命令展示
        display_cmd = _mask_cmd_for_display(cmd)
        _safe_log(
            self.log,
            f">>> {self._t('log_exec_cmd', 'Execute Command')}: {display_cmd}\n{'-' * 40}\n",
            "info",
        )

        error_detected = False
        return_code = None
        try:
            # 创建子进程
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=self.startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if self.system == "Windows" else 0
            )
            if controller:
                controller._set_proc(self.process)

            # 实时读取输出
            assert self.process.stdout is not None
            for raw_line in self.process.stdout:
                line = raw_line.strip()
                if not line:
                    continue

                lower_line = line.lower()
                # 扩展错误嗅探关键词
                if any(k in lower_line for k in
                       ["error", "403 forbidden", "command not found", "unable to download", "failed", "exception"]):
                    _safe_log(self.log, line + "\n", "error")
                    error_detected = True
                else:
                    _safe_log(self.log, line + "\n", None)

            self.process.wait()
            return_code = self.process.returncode

            success = (return_code == 0 and not error_detected)
            if success:
                _safe_log(self.log, self._t('log_download_success', '\n>>> 🎉 Download Success!\n'), "success")
            else:
                _safe_log(self.log, self._t('log_download_fail', '\n>>> ❌ Download Failed.\n'), "error")

            return success, return_code

        except FileNotFoundError as e:
            _safe_log(self.log, self._t('log_exec_not_found', '>>> ❌ Executable not found: {e}\n', e=e), "error")
            return False, None
        except Exception as e:
            _safe_log(self.log, self._t('log_exception_generic', '>>> ❌ Exception occurred: {e}\n', e=e), "error")
            return False, None
        finally:
            self.process = None

    def run_threaded(self, url: str, options: dict) -> DownloadController:
        """
        在后台线程中运行下载。返回一个 DownloadController 对象，调用者可以通过 controller.stop() 终止任务。
        """
        controller = DownloadController()

        def worker():
            success = False
            rc = None
            try:
                success, rc = self.run(url, options, controller)
            except Exception:
                success = False
                rc = None
            finally:
                controller._set_proc(None)
                self._notify_done(success, rc)

        th = threading.Thread(target=worker, daemon=True)
        controller._set_thread(th)
        th.start()
        return controller
