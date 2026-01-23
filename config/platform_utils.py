# core/platform_utils.py
import os, sys, subprocess, platform

def get_base_path():
    """
        返回程序的基础目录：
        - 如果使用 PyInstaller 打包，返回 exe 所在目录
        - 否则返回当前文件的父目录（即项目 package 目录）
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def is_cmd_available(cmd: str) -> bool:
    """
        简单判断命令行工具是否可用（通过 `--version` 迅速探测）。
        返回 True/False，调用方可据此决定是否提示安装/自动安装。
    """
    if not cmd:
        return False
    try:
        subprocess.run([cmd, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return True
    except Exception:
        return False

def ensure_mac_homebrew_paths():
    """
        在 macOS 下把常见 Homebrew 路径加入 PATH，避免 GUI 启动时 PATH 不完整的问题。
        这会直接改变 os.environ['PATH']，调用前请谨慎（或把结果传给子进程 env）。
    """
    if platform.system() != "Darwin":
        return
    p = os.environ.get("PATH", "")
    additions = ["/opt/homebrew/bin", "/usr/local/bin"]
    for add in additions:
        if add not in p:
            p += os.pathsep + add
    os.environ["PATH"] = p
