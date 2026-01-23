# utils/platform_utils.py
import os
import platform
import subprocess
import sys


def get_base_path():
    """
        返回程序的基础目录：
        - 如果使用 PyInstaller 打包，返回 exe 所在目录
        - 否则返回当前文件的父目录（即项目 package 目录）
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def setup_env_path():
    """
        在 macOS 下把常见 Homebrew 路径加入 PATH，避免 GUI 启动时 PATH 不完整的问题。
        这会直接改变 os.environ['PATH']，调用前请谨慎（或把结果传给子进程 env）。
    """
    if platform.system() != "Darwin":
        return
    current_path = os.environ.get("PATH", "")
    new_paths = ["/opt/homebrew/bin", "/usr/local/bin"]
    for add in new_paths:
        if add not in current_path:
            current_path += os.pathsep + add
    os.environ["PATH"] = current_path


def open_download_folder(path):
    """
    :param path: where the download folder is located
    :return: open or not
    for opening the download folder
    """
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except:
            return False, f"Path not created: {path}"

    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":
            subprocess.run(["open", path], check=True)
        else:
            subprocess.run(["xdg-open", path], check=True)
        return True, ""
    except Exception as e:
        return False, str(e)


def is_cmd_available(cmd: str) -> bool:
    """
        简单判断命令行工具是否可用（通过 `--version` 迅速探测）。
        返回 True/False，调用方可据此决定是否提示安装/自动安装。
    """
    if not cmd:
        return False
    try:
        subprocess.run(
            [cmd, "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False
        )
        return True
    except Exception:
        return False
