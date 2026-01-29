import ctypes
import platform
import sys

from PySide6.QtWidgets import QApplication

from ui.app_window import MainWindow


def _enable_windows_dpi_awareness():
    """Enable high-DPI awareness on Windows to avoid blurry UI."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main():
    # Enable high-DPI support on Windows
    if platform.system() == "Windows":
        _enable_windows_dpi_awareness()

    # Create Qt application
    app = QApplication(sys.argv)

    # Create and show main window (Qt Widgets only)
    window = MainWindow()
    window.show()

    # Enter Qt event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
