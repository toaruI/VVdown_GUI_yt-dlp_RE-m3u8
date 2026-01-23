# core/downloader.py
"""
Downloader module
- Exports: run_download_threaded(...) and run_download_sync(...)
- Callers provide log_cb(message: str, level: Optional[str]) and on_done(success: bool, returncode: int)
"""

from typing import Callable, Optional, List
import subprocess
import platform
import threading
import shlex
import os

LogCb = Callable[[str, Optional[str]], None]
DoneCb = Callable[[bool, int], None]

def _ensure_windows_startupinfo():
    startupinfo = None
    if platform.system() == "Windows":
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        except Exception:
            startupinfo = None
    return startupinfo

def _quote_arg(a: str) -> str:
    # Use shlex.quote for safety on *nix, keep as-is for Windows where necessary.
    try:
        return shlex.quote(a)
    except Exception:
        return '"{}"'.format(a.replace('"', '\\"'))

def build_command(
    url: str,
    download_dir: str,
    engine: str,
    thread_num: int,
    cookie_source: Optional[str] = None,
    cookie_file_path: Optional[str] = None,
    re_path: Optional[str] = None,
) -> List[str]:
    """
    Build a command list for subprocess based on the chosen engine.
    engine: 'yt-dlp' (default), 'aria2' (yt-dlp + aria2c), 're' (N_m3u8DL-RE local)
    """
    if engine == "re":
        if not re_path:
            raise ValueError("re_path required for engine='re'")
        # Example minimal args for N_m3u8DL-RE (adjust to your preferred flags)
        cmd = [re_path, url, "--save-dir", download_dir, "--thread-count", str(thread_num), "--no-log"]
        return cmd

    # Default to yt-dlp
    cmd = ["yt-dlp", "-P", download_dir, "--merge-output-format", "mp4", "--retries", "10", "-f", "bv+ba/b", url]

    if engine == "aria2":
        # instruct yt-dlp to use aria2c as external downloader with some args
        aria2_args = f"-x {max(1, int(thread_num))} -k 1M"
        cmd += ["--downloader", "aria2c", "--downloader-args", f"aria2c:{aria2_args}"]

    # cookie handling: prefer cookies-from-browser, else file
    if cookie_source in ("chrome", "edge", "safari", "firefox"):
        cmd += ["--cookies-from-browser", cookie_source]
    elif cookie_source == "file" and cookie_file_path:
        cmd += ["--cookies", cookie_file_path]

    return cmd

def run_download_sync(
    url: str,
    download_dir: str,
    engine: str,
    thread_num: int,
    cookie_source: Optional[str],
    cookie_file_path: Optional[str],
    re_path: Optional[str],
    log_cb: LogCb,
    on_done: DoneCb,
    env: Optional[dict] = None,
    cwd: Optional[str] = None,
    text_mode: bool = True,
    check_for_errors: bool = True,
):
    """
    Run the download command synchronously. Streams stdout/stderr to log_cb line by line.
    on_done(success: bool, returncode: int) is called when finished.
    """
    try:
        cmd = build_command(url, download_dir, engine, thread_num, cookie_source, cookie_file_path, re_path)
    except Exception as e:
        log_cb(f"[downloader] build_command error: {e}\n", "error")
        on_done(False, -1)
        return

    log_cb("[downloader] Execute:\n  " + " ".join(_quote_arg(x) for x in cmd) + "\n", "info")

    startupinfo = _ensure_windows_startupinfo()
    # Use a copy of os.environ merged with provided env
    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=text_mode,
            bufsize=1,
            env=run_env,
            cwd=cwd,
            startupinfo=startupinfo
        )
    except FileNotFoundError as e:
        log_cb(f"[downloader] executable not found: {e}\n", "error")
        on_done(False, -1)
        return
    except Exception as e:
        log_cb(f"[downloader] failed to start process: {e}\n", "error")
        on_done(False, -1)
        return

    error_detected = False
    try:
        # Stream lines as they appear
        if proc.stdout is not None:
            for raw_line in proc.stdout:
                line = raw_line.rstrip("\n")
                # Forward line to UI
                log_cb(line + "\n", None)

                # Lightweight error heuristics (customize as needed)
                lower = line.lower()
                if check_for_errors and ("error" in lower or "not found" in lower or "403" in line or "failed" in lower):
                    error_detected = True
    except Exception as e:
        log_cb(f"[downloader] reading output failed: {e}\n", "error")
    finally:
        proc.wait()
        rc = proc.returncode
        success = (rc == 0) and (not error_detected)
        on_done(success, rc)

def run_download_threaded(
    url: str,
    download_dir: str,
    engine: str,
    thread_num: int,
    cookie_source: Optional[str],
    cookie_file_path: Optional[str],
    re_path: Optional[str],
    log_cb: LogCb,
    on_done: DoneCb,
    env: Optional[dict] = None,
    cwd: Optional[str] = None,
    daemon: bool = True,
):
    """
    Convenience wrapper: runs run_download_sync in a separate thread so caller (UI) doesn't block.
    Returns the Thread object (so caller can join/cancel if needed).
    """
    def target():
        run_download_sync(
            url=url,
            download_dir=download_dir,
            engine=engine,
            thread_num=thread_num,
            cookie_source=cookie_source,
            cookie_file_path=cookie_file_path,
            re_path=re_path,
            log_cb=log_cb,
            on_done=on_done,
            env=env,
            cwd=cwd
        )

    th = threading.Thread(target=target, daemon=daemon)
    th.start()
    return th
