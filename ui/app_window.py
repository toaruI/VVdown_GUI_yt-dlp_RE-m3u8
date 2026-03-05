# -*- coding: utf-8 -*-
"""
PySide6 MainWindow
- Default language: English
- Language switching syncs UI / downloader / installer
- Refactored into separate managers for maintainability
"""

import os
from PySide6.QtCore import Qt, Signal, Slot, QThreadPool
from PySide6.QtWidgets import QWidget, QGraphicsDropShadowEffect, QApplication
from PySide6.QtGui import QColor

from config.config import TRANSLATIONS, SYSTEM, load_user_config, save_user_config
from core.downloader import DownloaderEngine
from core.installer import DependencyInstaller
from utils import setup_env_path
from .widgets import setup_styles
from .main_window_ui import MainWindowUI

from .theme_manager import ThemeManager
from .cookie_manager import CookieManager
from .ui_state_manager import UIStateManager
from .dependency_handler import DependencyHandler
from .download_handler import DownloadHandler

class MainWindow(QWidget):
    installer_finished_signal = Signal(bool)
    log_signal = Signal(str, str)
    download_finished_signal = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        try:
            QApplication.setStyle("Fusion")
        except Exception:
            pass
            
        self.system = SYSTEM

        # ---- config ----
        self.config_data = load_user_config()
        self.lang = self.config_data.get("lang", "en")
        self.theme = self.config_data.get("theme", "dark")
        self.download_dir = self.config_data.get("download_dir", os.path.expanduser("~/Downloads"))
        self.cookie_file_path = self.config_data.get("cookie_path", "")

        default_cookie = self.config_data.get("cookie_source")
        if not default_cookie:
            if self.system == "Darwin":
                default_cookie = "safari"
            elif self.system == "Windows":
                default_cookie = "chrome"
            else:
                default_cookie = "firefox"
        self.cookie_source = default_cookie

        # ---- env ----
        setup_env_path()
        self.font_ui, self.font_bold, self.font_log = setup_styles(self.system)
        self.cmd_key = "Command" if self.system == "Darwin" else "Control"

        # ---- Handlers Initialization (early so ui setup can access them if needed) ----
        self.theme_manager = ThemeManager(self)
        try:
            self.theme_manager.apply_full_theme(first_time=True)
        except Exception:
            pass
        self.cookie_manager = CookieManager(self)
        self.ui_state_manager = UIStateManager(self)
        self.dependency_handler = DependencyHandler(self)
        self.download_handler = DownloadHandler(self)

        # ---- core ----
        self.download_controller = None
        self.downloader = DownloaderEngine(
            self.log_thread_safe,
            translations=TRANSLATIONS,
            lang=self.lang,
        )
        self.downloader.on_done = self.on_download_done

        self.installer = DependencyInstaller(
            self.log_thread_safe,
            translations=TRANSLATIONS,
            lang=self.lang,
        )

        self._aria2_available = True
        self.threadpool = QThreadPool.globalInstance()

        # ---- ui ----
        self._build_ui()

        # ---- premium shadow (macOS/Windows) ----
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(24)
        self.shadow.setXOffset(0)
        self.shadow.setYOffset(6)
        self.shadow.setColor(QColor(0, 0, 0, 80))
        self._content.setGraphicsEffect(self.shadow)

        # ---- theme ----
        self.theme_manager.apply_full_theme(first_time=False)
        self.update_config("theme", self.theme)

        self.ui_state_manager.restore_config_state()
        self.dependency_handler.check_deps_on_start()
        
        # Connect Signals
        self.log_signal.connect(self._append_log)
        self.download_finished_signal.connect(self.download_handler.handle_download_done)
        self.installer_finished_signal.connect(self.dependency_handler.on_installer_finished)

        # Ensure download button state is correct on startup
        self.cookie_manager.update_download_enabled()

    # ---------------- helpers ----------------
    def get_current_trans(self):
        return TRANSLATIONS.get(self.lang, TRANSLATIONS["en"])

    def update_config(self, key, value):
        self.config_data[key] = value
        save_user_config(self.config_data)

    def log_thread_safe(self, text, tag=None):
        self.log_signal.emit(text, tag or "info")

    @Slot(str, str)
    def _append_log(self, text, tag):
        prefix = {"error": "❌ ", "success": "✅ ", "warning": "⚠️ "}.get(tag, "")
        self.log_text.appendPlainText(prefix + text)
        self.log_text.setMaximumBlockCount(1000)

    # ---------------- UI ----------------
    def _build_ui(self):
        self.ui = MainWindowUI()
        self.ui.setup_ui(self)

    # ---------------- Delegate methods used by UI elements ----------------
    def _os_supported_browsers(self):
        from config.config import IS_MAC, IS_WIN
        if IS_MAC:
            return {"safari", "chrome", "firefox"}
        elif IS_WIN:
            return {"chrome", "edge", "firefox"}
        else:
            return {"chrome", "firefox"}

    def _set_cookie_source(self, source: str):
        self.cookie_manager.set_cookie_source(source)

    def toggle_engine_ui(self):
        self.ui_state_manager.toggle_engine_ui()

    def toggle_download(self):
        self.download_handler.toggle_download()

    def on_download_done(self, success, rc=None):
        self.download_finished_signal.emit(bool(success))

    def run_install(self):
        self.dependency_handler.run_install()

    def change_language(self):
        self.ui_state_manager.change_language()

    def select_cookie_file(self):
        self.cookie_manager.select_cookie_file()

    def change_download_path(self):
        from PySide6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(self, "Select download folder", self.download_dir)
        if d:
            self.download_dir = d
            self.path_label.setText(d[-30:])
            self.update_config("download_dir", d)

    def open_cookie_plugin(self):
        self.cookie_manager.open_cookie_plugin()

    def open_catcatch(self):
        self.cookie_manager.open_catcatch()

    def change_theme(self):
        self.theme_manager.change_theme()
