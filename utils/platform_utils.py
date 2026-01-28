# utils/platform_utils.py
# Cross-platform helpers for filesystem, PATH setup, and command availability
import os
import subprocess
import sys
from config.config import SYSTEM, IS_MAC, IS_WIN, IS_LINUX


def get_base_path():
    """
    Return the base directory of the application:
    - If running as a PyInstaller frozen executable, return the directory of the executable
    - Otherwise, return the directory of this file (project package root)
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def setup_env_path():
    """
    On macOS, append common Homebrew paths to PATH.
    This is necessary because GUI-launched apps often inherit a minimal PATH.

    NOTE:
    - This mutates os.environ['PATH'] globally
    - Call with care, or pass PATH explicitly to subprocesses
    """
    if not IS_MAC:
        return
    current_path = os.environ.get("PATH", "")
    extra_paths = ["/opt/homebrew/bin", "/usr/local/bin"]

    for p in extra_paths:
        if p not in current_path:
            current_path = current_path + os.pathsep + p

    os.environ["PATH"] = current_path


def open_download_folder(path):
    """
    Open the given folder in the system file manager.

    :param path: Target directory to open
    :return: (success: bool, error_message: str)
    """
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except:
            return False, f"Path not created: {path}"

    try:
        if IS_WIN:
            os.startfile(path)
        elif IS_MAC:
            subprocess.run(["open", path], check=True)
        else:
            # Linux and other Unix-like systems
            subprocess.run(["xdg-open", path], check=True)
        return True, ""
    except Exception as e:
        return False, str(e)


def is_cmd_available(cmd: str) -> bool:
    """
    Check whether a command-line tool is available.

    The check is performed by invoking `<cmd> --version` and suppressing output.
    Returns True if the command can be executed, otherwise False.
    """
    if not cmd:
        return False
    try:
        subprocess.run(
            [cmd, "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=3
        )
        return True
    except Exception:
        return False
