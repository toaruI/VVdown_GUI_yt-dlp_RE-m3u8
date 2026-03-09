# -*- coding: utf-8 -*-
"""
PySide6 MainWindow
- Default language: English
- Language switching syncs UI / downloader / installer
- Refactored into separate managers for maintainability
"""

import os

from PySide6.QtCore import Qt, Signal, Slot, QThreadPool
from PySide6.QtWidgets import QWidget, QApplication

from config.config import TRANSLATIONS, SYSTEM, load_user_config, save_user_config
from core.downloader import DownloaderEngine
from core.installer import DependencyInstaller
from utils import setup_env_path
from .cookie_manager import CookieManager
from .dependency_handler import DependencyHandler
from .download_handler import DownloadHandler
from .main_window_ui import MainWindowUI
from .resize_handler import ResizeHandler
from .theme_manager import ThemeManager
from .ui_state_manager import UIStateManager
from .widgets import setup_styles


class MainWindow(QWidget):
    installer_finished_signal = Signal(bool)
    log_signal = Signal(str, str)
    download_finished_signal = Signal(bool)

    RESIZE_BORDER = 6
    NORMAL_MARGINS = (6, 6, 6, 6)  # >= RESIZE_BORDER
    MAXIMIZED_MARGINS = (0, 0, 0, 0)
    LOG_PREFIX = {"error": "❌ ", "success": "✅ ", "warning": "⚠️ "}

    def __init__(self, parent=None):
        super().__init__(parent)

        self._setup_window()
        self._load_config()
        self._init_runtime_state()
        self._setup_environment()
        self._init_managers()
        self._init_core_engines()
        self._build_ui()
        self._apply_initial_state()
        self._connect_signals()

    def _setup_window(self):
        self.setObjectName("MainWindow")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("QWidget#MainWindow { background-color: rgba(0, 0, 0, 1); }")
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        try:
            QApplication.setStyle("Fusion")
        except Exception:
            pass

    def _load_config(self):
        self.system = SYSTEM
        self.config_data = load_user_config()
        self.lang = self.config_data.get("lang", "en")
        self.theme = self.config_data.get("theme", "dark")
        self.download_dir = self.config_data.get(
            "download_dir", os.path.expanduser("~/Downloads")
        )
        self.cookie_file_path = self.config_data.get("cookie_path", "")
        self.cookie_source = self._resolve_default_cookie()

    def _resolve_default_cookie(self) -> str:
        source = self.config_data.get("cookie_source")
        if source:
            return source
        defaults = {"Darwin": "safari", "Windows": "chrome"}
        return defaults.get(self.system, "firefox")

    def _init_runtime_state(self):
        """presume nothing is correct and prepare for all scenarios, including first run with missing deps"""
        self._win_cookie_warned: bool = False
        self._local_cookie_warned: bool = False
        self._last_lang_logged: str | None = None
        self._hover_fix_applied: bool = False
        self._aria2_available: bool = True
        self.download_controller = None
        self.resize_handler = None

    def _setup_environment(self):
        setup_env_path()
        self.font_ui, self.font_bold, self.font_log = setup_styles(self.system)
        self.cmd_key = "Command" if self.system == "Darwin" else "Control"

    def _init_managers(self):
        self.theme_manager = ThemeManager(self)
        self.cookie_manager = CookieManager(self)
        self.ui_state_manager = UIStateManager(self)
        self.dependency_handler = DependencyHandler(self)
        self.download_handler = DownloadHandler(self)
        self.resize_handler = ResizeHandler(self, border_width=self.RESIZE_BORDER)

    def _init_core_engines(self):
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
        self.threadpool = QThreadPool.globalInstance()

    def _apply_initial_state(self):
        self.theme_manager.apply_full_theme(first_time=False)
        self.update_config("theme", self.theme)
        self.ui_state_manager.restore_config_state()
        self.dependency_handler.check_deps_on_start()
        self.cookie_manager.update_download_enabled()

    def _connect_signals(self):
        self.log_signal.connect(self._append_log)
        self.download_finished_signal.connect(
            self.download_handler.handle_download_done
        )
        self.installer_finished_signal.connect(
            self.dependency_handler.on_installer_finished
        )

    # ---------------- helpers ----------------
    def get_current_trans(self):
        return TRANSLATIONS.get(self.lang, TRANSLATIONS["en"])

    def update_config(self, key, value):
        self.config_data[key] = value
        save_user_config(self.config_data)

    def log_thread_safe(self, text, tag=None):
        self.log_signal.emit(text, tag or "info")

    def is_downloading(self) -> bool:
        ctrl = self.download_controller
        if ctrl is None:
            return False
        if hasattr(ctrl, "is_running"):
            return ctrl.is_running()
        # Fallback: if the controller has a _proc attribute, we assume it's running
        return getattr(ctrl, "_proc", None) is not None

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

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_hover_fix_applied", False):
            self._hover_fix_applied = True
            self.ui_state_manager.apply_mac_hover_fix()

    # ---- mouse events ----

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.resize_handler:
            if self.resize_handler.try_start_resize(event):
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resize_handler:
            if self.resize_handler.handle_resize(event):
                return
            if not event.buttons():
                self.resize_handler.update_cursor(event.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.resize_handler and self.resize_handler.end_resize():
            return
        super().mouseReleaseEvent(event)
