# core/downloader.py
import os
import subprocess
import platform
import threading
import signal
from typing import Callable, Optional, Tuple

from config import BIN_DIR
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
            system = platform.system()
            if system == "Windows":
                # 强杀进程树
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                try:
                    proc.terminate()
                except Exception:
                    proc.kill()
        except Exception:
            # 忽略任何停止时的异常
            pass


class DownloaderEngine:
    def __init__(self, log_callback: LogCb):
        """
        :param log_callback: 一个函数，接收 (text, tag)，用于将日志发回 UI
                             tag 建议使用: "info", "warning", "error", "success" 或 None
        """
        self.log = log_callback
        self.process: Optional[subprocess.Popen] = None
        self.system = platform.system()

        # Windows 隐藏控制台窗口的标志（保留旧版行为）
        self.startupinfo = None
        if self.system == "Windows":
            try:
                self.startupinfo = subprocess.STARTUPINFO()
                self.startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            except Exception:
                self.startupinfo = None

    def _check_common_tools(self, engine: str):
        """
        检查常用外部命令是否可用，并在日志中给出提示（但不强制失败）。
        """
        # 检查 yt-dlp
        if engine in ("native", "aria2"):
            if not is_cmd_available("yt-dlp"):
                _safe_log(self.log, "⚠️ 未在 PATH 中找到 yt-dlp，下载可能无法执行。", "warning")
        if engine == "re":
            re_exe = "N_m3u8DL-RE.exe" if self.system == "Windows" else "N_m3u8DL-RE"
            re_path = os.path.join(BIN_DIR, re_exe)
            if not os.path.exists(re_path) and not is_cmd_available("N_m3u8DL-RE"):
                _safe_log(self.log, "❌ Error: 未找到 N_m3u8DL-RE，请点击顶部【修复依赖】或把可执行文件放入 bin。", "error")
        if engine == "aria2":
            if not is_cmd_available("aria2c"):
                _safe_log(self.log, "⚠️ 未检测到 aria2c，Aria2 加速将无法使用（请安装 aria2 并确保在 PATH 中）。", "warning")

    def _build_command(self, url: str, engine: str, save_dir: str,
                       cookie_src: str, cookie_path: str, threads: int) -> Tuple[list, Optional[str]]:
        """
        构建要执行的命令列表，并返回 (cmd_list, maybe_cookie_header_str)
        如果需要向 RE 注入 header，则 cookie_header_str 为 "Cookie: k=v; k2=v2" 格式，否则为 None。
        """
        cmd = []
        cookie_header = None

        if engine == "re":
            # N_m3u8DL-RE
            re_exe = "N_m3u8DL-RE.exe" if self.system == "Windows" else "N_m3u8DL-RE"
            re_path = os.path.join(BIN_DIR, re_exe)
            exe_cmd = re_path if os.path.exists(re_path) else "N_m3u8DL-RE"

            cmd = [
                exe_cmd,
                url,
                "--save-dir", save_dir,
                "--thread-count", str(threads),
                "--auto-select",
                "--no-log"  # 禁用 RE 自己的日志文件，直接读 stdout
            ]

            # RE 要求 Cookie 注入为 Header 格式 "k=v; k2=v2"
            if cookie_src == "file" and cookie_path:
                _safe_log(self.log, ">>> 正在解析 Cookie 文件以适配 RE 引擎...\n", "info")
                cookie_str = None
                try:
                    cookie_str = parse_cookie_file(cookie_path, url)
                except Exception as e:
                    _safe_log(self.log, f">>> ⚠️ 解析 Cookie 文件时发生异常: {e}\n", "warning")
                if cookie_str:
                    cookie_header = f"Cookie: {cookie_str}"
                    cmd.extend(["--header", cookie_header])
                    _safe_log(self.log, ">>> Cookie 解析成功，已注入 Header\n", "success")
                else:
                    _safe_log(self.log, ">>> ⚠️ Cookie 解析结果为空或不匹配当前域名，尝试无 Cookie 下载\n", "warning")
            elif cookie_src in ["chrome", "edge", "safari", "firefox"]:
                _safe_log(self.log, "⚠️ RE 引擎不支持直接读取浏览器 Cookie，请使用【Cookie插件】导出 txt 文件。\n", "warning")
                _safe_log(self.log, ">>> 将尝试无 Cookie 下载...\n", "warning")

        else:
            # yt-dlp 路径
            cmd = [
                "yt-dlp",
                "-P", save_dir,
                "--merge-output-format", "mp4",
                "--retries", "10",
                "-f", "bv+ba/b",
                url
            ]

            if engine == "aria2":
                cmd.extend([
                    "--downloader", "aria2c",
                    "--downloader-args", f"aria2c:-x {threads} -k 1M"
                ])
                _safe_log(self.log, f">>> 启用 Aria2 加速 (线程: {threads})\n", "info")

            if cookie_src == "file" and cookie_path:
                cmd.extend(["--cookies", cookie_path])
                _safe_log(self.log, f">>> 已加载 Cookie 文件: {os.path.basename(cookie_path)}\n", "info")
            elif cookie_src in ["chrome", "edge", "safari", "firefox"]:
                cmd.extend(["--cookies-from-browser", cookie_src])
                _safe_log(self.log, f">>> 尝试读取浏览器 Cookie: {cookie_src}\n", "info")

        return cmd, cookie_header

    def run(self, url: str, options: dict) -> bool:
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
            threads = int(options.get("threads", 4))
        except Exception:
            threads = 4

        # 工具检查提示（不会直接抛错）
        self._check_common_tools(engine)

        # 构建命令
        cmd, cookie_header = self._build_command(url, engine, save_dir, cookie_src, cookie_path, threads)

        # 脱敏后的命令展示
        display_cmd = _mask_cmd_for_display(cmd)
        _safe_log(self.log, f"Execute: {display_cmd}\n{'-' * 40}\n", "info")

        error_detected = False
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

            # 实时读取输出
            assert self.process.stdout is not None
            for raw_line in self.process.stdout:
                line = raw_line.strip()
                if not line:
                    continue

                lower_line = line.lower()
                # 扩展错误嗅探关键词
                if any(k in lower_line for k in ["error", "403 forbidden", "command not found", "unable to download", "failed", "exception"]):
                    _safe_log(self.log, line + "\n", "error")
                    error_detected = True
                else:
                    _safe_log(self.log, line + "\n", None)

            self.process.wait()
            return_code = self.process.returncode

            if return_code == 0 and not error_detected:
                _safe_log(self.log, "\n>>> 🎉 下载任务完成！\n", "success")
                return True
            else:
                _safe_log(self.log, f"\n>>> ❌ 下载结束，但似乎发生了错误 (Code: {return_code})\n", "error")
                return False

        except FileNotFoundError as e:
            _safe_log(self.log, f"\n>>> ❌ 可执行文件未找到: {e}\n", "error")
            return False
        except Exception as e:
            _safe_log(self.log, f"\n>>> ❌ 发生异常: {e}\n", "error")
            return False
        finally:
            self.process = None

    def run_threaded(self, url: str, options: dict) -> DownloadController:
        """
        在后台线程中运行下载。返回一个 DownloadController 对象，调用者可以通过 controller.stop() 终止任务。
        """
        controller = DownloadController()

        def worker():
            # 在子线程内调用同步 run，但通过 controller._set_proc 将进程引用暴露给外部
            engine = options.get("engine", "native")
            save_dir = options.get("download_dir", ".")
            cookie_src = options.get("cookie_source", "none")
            cookie_path = options.get("cookie_path", "")
            try:
                threads = int(options.get("threads", 4))
            except Exception:
                threads = 4

            # 构建命令（和 run 中一致）
            self._check_common_tools(engine)
            cmd, cookie_header = self._build_command(url, engine, save_dir, cookie_src, cookie_path, threads)
            display_cmd = _mask_cmd_for_display(cmd)
            _safe_log(self.log, f"Execute: {display_cmd}\n{'-' * 40}\n", "info")

            try:
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
                # 将 proc 暴露给 controller 和实例 self.process（方便兼容旧逻辑）
                controller._set_proc(proc)
                self.process = proc

                assert proc.stdout is not None
                error_detected = False
                for raw_line in proc.stdout:
                    line = raw_line.strip()
                    if not line:
                        continue
                    lower_line = line.lower()
                    if any(k in lower_line for k in ["error", "403 forbidden", "command not found", "unable to download", "failed", "exception"]):
                        _safe_log(self.log, line + "\n", "error")
                        error_detected = True
                    else:
                        _safe_log(self.log, line + "\n", None)

                proc.wait()
                return_code = proc.returncode
                if return_code == 0 and not error_detected:
                    _safe_log(self.log, "\n>>> 🎉 下载任务完成！\n", "success")
                else:
                    _safe_log(self.log, f"\n>>> ❌ 下载结束，但似乎发生了错误 (Code: {return_code})\n", "error")
            except FileNotFoundError as e:
                _safe_log(self.log, f"\n>>> ❌ 可执行文件未找到: {e}\n", "error")
            except Exception as e:
                _safe_log(self.log, f"\n>>> ❌ 发生异常: {e}\n", "error")
            finally:
                # 清理
                controller._set_proc(None)
                self.process = None

        th = threading.Thread(target=worker, daemon=True)
        controller._set_thread(th)
        th.start()
        return controller

    def stop(self):
        """
        兼容旧接口：停止当前 process（如果有的话）
        """
        if self.process:
            _safe_log(self.log, "\n>>> 正在终止进程...\n", "warning")
            try:
                if self.system == "Windows":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    try:
                        self.process.terminate()
                    except Exception:
                        try:
                            self.process.kill()
                        except Exception:
                            pass
            except Exception:
                pass
