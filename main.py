import ctypes
import platform
import sys

from PySide6.QtWidgets import QApplication

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

    # 2. 创建 Qt 应用（⚠️ 不再使用 tkinter）
    app = QApplication(sys.argv)

    # 3. 创建主窗口（Qt Widget，不要传 Tk root）
    win = MainWindow()
    win.show()

    # 4. 进入 Qt 事件循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
