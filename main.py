import tkinter as tk
import ctypes
import platform
from ui.app_window import MainWindow


def main():
    # 1. 针对 Windows 的高分屏(DPI) 适配
    # 如果不加这段，Windows 上界面可能会模糊
    if platform.system() == "Windows":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    # 2. 创建根窗口
    root = tk.Tk()

    # 3. 初始化主界面逻辑
    app = MainWindow(root)

    # 4. 进入主循环
    root.mainloop()


if __name__ == "__main__":
    main()