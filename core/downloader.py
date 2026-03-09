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

    def is_running(self) -> bool:
        with self._lock:
            return self._proc is not None

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
            # ignore any errors during termination (e.g. process already exited)
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
        import time

        try:
            from config.config import USER_CONFIG_DIR
            base = Path(USER_CONFIG_DIR)
            base.mkdir(parents=True, exist_ok=True)
            out_file = base / f"cookies_{browser}.txt"

            print(f"[DEBUG bootstrap] out_file={out_file}")
            print(f"[DEBUG bootstrap] exists={out_file.exists()}")

            FRESH_SECONDS = 3600  # 约 60 分钟内的缓存都认为是新鲜的，避免频繁调用 yt-dlp 导出
            if out_file.exists() and (time.time() - out_file.stat().st_mtime) < FRESH_SECONDS:
                age = time.time() - out_file.stat().st_mtime
                if age < FRESH_SECONDS:
                    with open(out_file, 'r', encoding='utf-8', errors='ignore') as f:
                        first_line = f.readline().strip()
                    if first_line.startswith('# Netscape') or '\t' in first_line:
                        _safe_log(self.log,
                                  self._t('log_bootstrap_cookie_reuse',
                                          '>>> 🍪 Reusing cached cookies from {browser} ({age}s ago)\n',
                                          browser=browser, age=int(age)),
                                  "info")
                        return str(out_file)
                    else:
                        out_file.unlink(missing_ok=True)

            _safe_log(self.log,
                self._t('log_bootstrap_cookie_start',
                    '>>> 🍪 Extracting cookies from {browser}, please wait...\n',
                    browser = browser),
                "info")

            cmd = [
                "yt-dlp",
                "--cookies-from-browser", browser,
                "--cookies", str(out_file),
                "--skip-download",
                target_url,
            ]

            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

            if out_file.exists() and out_file.stat().st_size > 0:
                with open(out_file, 'r', encoding='utf-8', errors='ignore') as f:
                    first_line = f.readline().strip()

                if first_line.startswith('# Netscape') or '\t' in first_line:
                    _safe_log(self.log,
                              self._t('log_bootstrap_cookie_done',
                                      '>>> 🍪 Extracted cookies from {browser} cache\n',
                                      browser=browser),
                              "success")
                    return str(out_file)

                else:
                    _safe_log(self.log,
                              self._t('log_bootstrap_cookie_fail',
                                      '>>> ⚠️ Cookie file format invalid from {browser}\n',
                                      browser=browser),
                              "warning")
                    out_file.unlink(missing_ok=True)
            else:
                _safe_log(self.log,
                          self._t('log_bootstrap_cookie_fail',
                                  '>>> ⚠️ No cookies extracted from {browser}.\n'
                                  '    Tip: Try using the "Get cookies.txt" button to export manually.\n',
                                  browser=browser),
                          "warning")

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

    def _resolve_cookie(self, cookie_src: str, cookie_path: str, url: str):
        """
        统一解析 Cookie，返回 (cookie_str, cookie_file_path, browser_fallback)
        - cookie_str: "k=v; k2=v2" 格式，用于 header 注入
        - cookie_file_path: cookies.txt 文件路径，用于 --cookies 参数

        返回 (None, None, None) 表示无可用 Cookie
        """
        # Guest mode do not use cookies
        if cookie_src == "none":
            return None, None, None

        #print(f"[DEBUG _resolve_cookie] cookie_src={cookie_src}, cookie_path={cookie_path}")
        #print(f"[DEBUG _resolve_cookie] COOKIE_PERSISTENT_CACHE_ENABLED={COOKIE_PERSISTENT_CACHE_ENABLED}")

        # try persistent cache first (only if cookie_path is provided.
        # otherwise skip to avoid unnecessary file access)
        if COOKIE_PERSISTENT_CACHE_ENABLED and cookie_path:
            try:
                cookie_str = parse_cookie_file(cookie_path, url)

                print(
                    f"[DEBUG _resolve_cookie] parse_cookie_file returned: len={len(cookie_str) if cookie_str else 'None'}")
                print(f"[DEBUG _resolve_cookie] cookie_str preview: '{(cookie_str or '')[:100]}'")

                if cookie_str:
                    _safe_log(self.log,
                              self._t('log_cookie_match',
                                      '>>> Loaded {count} cookies from cache\n',
                                      count=len(cookie_str)),
                              "success")
                    return cookie_str, cookie_path, None
            except Exception as e:
                print(f"[DEBUG _resolve_cookie] parse EXCEPTION: {e}")
                _safe_log(self.log,
                          self._t('log_cookie_parse_error',
                                  '>>> Failed to parse cookie file: {e}\n', e=e),
                          "warning")

        if cookie_src == "file" and cookie_path:
            try:
                _safe_log(self.log,
                          self._t('log_cookie_filter',
                                  '>>> Filtering cookies for target host: {host}...\n', host=""),
                          "info")
                cookie_str = parse_cookie_file(cookie_path, url)
                if cookie_str:
                    _safe_log(self.log,
                              self._t('log_cookie_match',
                                      '>>> Loaded {count} cookies from file\n', count=len(cookie_str)),
                              "success")
                    return cookie_str, cookie_path, None
                else:
                    _safe_log(self.log,
                              self._t('log_cookie_none',
                                      ' No cookies found for {host}. Falling back to direct download.', host=""),
                              "warning")
            except Exception as e:
                _safe_log(self.log,
                          self._t('log_cookie_parse_error',
                                  '>>> Failed to parse cookie file: {e}\n', e=e),
                          "warning")

        # 浏览器 Cookie 回退
        if cookie_src in ("chrome", "edge", "firefox", "safari"):
            _safe_log(self.log,
                      self._t('log_cookie_fallback_browser',
                              '>>> Cookie cache miss, falling back to browser extraction (slow)\n'),
                      "warning")
            return None, None, cookie_src  # 返回浏览器名，让调用方决定如何使用

        return None, None, None

    def _inject_cookie_to_cmd(self, cmd: list, engine: str,
                              cookie_str: str | None,
                              cookie_file_path: str | None,
                              browser_fallback: str | None,
                              url: str):
        """
        根据引擎类型，将 Cookie 注入到命令中
        """
        if cookie_str:
            if engine == "re":
                header = f"Cookie: {cookie_str}"
                cmd.extend(["--header", header])
            else:
                if cookie_file_path:
                    cmd.extend(["--cookies", cookie_file_path])
                else:
                    # fallback to header injection if cookie file is not available (e.g. from browser bootstrap)
                    cmd.extend(["--add-header", f"Cookie: {cookie_str}"])
            return

        # 无 cookie_str，尝试浏览器回退（仅 yt-dlp 支持）
        if browser_fallback and engine != "re":
            if _is_twitter_url(url):
                _safe_log(self.log,
                          self._t('log_cookie_from_browser',
                                  '>>> Using browser cookies: {browser}\n',
                                  browser=browser_fallback),
                          "info")
            cmd.extend(["--cookies-from-browser", browser_fallback])
        elif browser_fallback and engine == "re":
            _safe_log(self.log,
                      self._t('log_re_no_browser',
                              '⚠️ RE engine does not support browser cookies.'),
                      "warning")

        elif not browser_fallback and engine != "re" and _is_twitter_url(url):
            _safe_log(self.log,
                      self._t('log_cookie_none',
                              '⚠️ Twitter/X requires browser cookies for authenticated access.'),
                      "warning")

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
        check for presence of required tools based on selected engine,
        and log warnings if not found. Does not raise exceptions, just logs.
        """
        # check yt-dlp
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
        build the command list based on engine and cookie strategy, and return (cmd_list, cookie_header_str)
            - cmd_list: the list of command arguments to execute
            - cookie_header_str: the actual "Cookie: k=v; ..." string injected into headers (for logging display), or None if no cookies used
        """

        print(f"[DEBUG _build_command] INITIAL cookie_path='{cookie_path}' (type={type(cookie_path)})")
        print(f"[DEBUG _build_command] not cookie_path = {not cookie_path}")
        print(
            f"[DEBUG _build_command] cookie_src in browsers = {cookie_src in ('chrome', 'edge', 'firefox', 'safari')}")


        if not cookie_path and cookie_src in ("chrome", "edge", "firefox", "safari"):
            print(f"[DEBUG _build_command] ENTERING bootstrap...")
            bootstrap_browser = cookie_src
            cookie_path = self._bootstrap_cookies_from_browser(bootstrap_browser, url)
            print(f"[DEBUG _build_command] bootstrap returned: '{cookie_path}'")
        else:
            print(f"[DEBUG _build_command] SKIPPED bootstrap")

        print(f"[DEBUG _build_command] after bootstrap: cookie_path={cookie_path}")
        print(f"[DEBUG _build_command] cookie_src={cookie_src}, engine={engine}")

        cookie_str, cookie_file, browser_fallback = self._resolve_cookie(cookie_src, cookie_path, url)

        if engine == "re":
            cmd, cookie_header = self._build_re_command(url, save_dir, threads)
        elif engine == "aria2":
            cmd, cookie_header = self._build_ytdlp_command(url, save_dir, aria2=True, threads=threads)
        else:
            cmd, cookie_header = self._build_ytdlp_command(url, save_dir, aria2=False, threads=threads)

        self._inject_cookie_to_cmd(cmd, engine, cookie_str, cookie_file, browser_fallback, url)

        if cookie_str and engine == "re":
            cookie_header = f"Cookie: {cookie_str}"

        return cmd, cookie_header

    def _build_re_command(self, url: str, save_dir: str, threads: int):
        """build the command list for N_m3u8DL-RE engine, and return (cmd_list, None) since RE doesn't support header injection"""

        def _is_stream_url(u: str) -> bool:
            ul = u.lower()
            return ul.endswith('.m3u8') or ul.endswith('.mpd') or 'm3u8' in ul

        if not _is_stream_url(url):
            raise ValueError("RE engine only supports stream URLs (m3u8/mpd).")

        re_exe = "N_m3u8DL-RE.exe" if self.system == "Windows" else "N_m3u8DL-RE"
        re_path = os.path.join(BIN_DIR, re_exe)
        exe_cmd = re_path if os.path.isfile(re_path) else "N_m3u8DL-RE"

        cmd = [
            exe_cmd, url,
            "--save-dir", save_dir,
            "--auto-select",
            "--no-log",
        ]

        if threads > 0:
            cmd.extend(["--thread-count", str(threads)])

        return cmd, None

    def _build_ytdlp_command(self, url: str, save_dir: str,
                             aria2: bool = False, threads: int = 0):
        """build the command list for yt-dlp engine, and return (cmd_list, None) since cookies are injected via --add-header or --cookies-from-browser"""
        yt_path = os.path.join(BIN_DIR, "yt-dlp.exe" if IS_WIN else "yt-dlp")
        yt_cmd = yt_path if os.path.isfile(yt_path) else "yt-dlp"

        cmd = [
            yt_cmd,
            "-P", save_dir,
            "--merge-output-format", "mp4",
            "--retries", "10",
            "-f", "bv+ba/b",
            url,
        ]

        if aria2:
            aria2_path = os.path.join(BIN_DIR, "aria2c.exe" if IS_WIN else "aria2c")
            aria2_cmd = aria2_path if os.path.isfile(aria2_path) else "aria2c"
            cmd.extend([
                "--downloader", aria2_cmd,
                "--downloader-args", f"{aria2_cmd}:-x {threads} -k 1M",
            ])
            _safe_log(self.log,
                      self._t('log_aria2_enabled',
                              '>>> Aria2 acceleration enabled (threads: {threads})\n',
                              threads=threads),
                      "info")

        return cmd, None

    def run(self, url: str, options: dict, controller: Optional['DownloadController'] = None) -> Tuple[
        bool, Optional[int]]:
        """
        执行下载命令并实时处理输出。返回 (success, return_code)。
            - success: True if download succeeded (exit code 0 and no error keywords detected), False otherwise
            - return_code: the actual exit code of the process, or None if process failed to start
            - controller: optional DownloadController instance to receive process reference for control (e.g. stop)
        """
        engine = options.get("engine", "native")
        save_dir = options.get("download_dir", ".")
        cookie_src = options.get("cookie_source", "none")
        cookie_path = options.get("cookie_path", "")
        # ensure threads is a non-negative integer, default to 0 (no extra threads) if invalid
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
        proc = None
        try:
            # 创建子进程
            proc = subprocess.Popen(
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
                controller._set_proc(proc)

            # 实时读取输出
            assert proc.stdout is not None
            for raw_line in proc.stdout:
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

            proc.wait()
            return_code = proc.returncode

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
            if controller:
                controller._set_proc(None)

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
