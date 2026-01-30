# -*- coding: utf-8 -*-
"""
PySide6 MainWindow
- Default language: English
- Language switching syncs UI / downloader / installer
- No hard-coded Chinese UI logs
"""

import os
import threading
import sys

# Add QMenu to QtWidgets imports
from PySide6.QtCore import Qt, Signal, Slot, QThreadPool, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QGroupBox, QRadioButton, QFileDialog, QPlainTextEdit,
    QSpinBox, QApplication, QMainWindow, QPushButton, QMenu,
    QSizePolicy,
)
# --- Custom title bar support ---
from PySide6.QtGui import QMouseEvent, QPalette, QPainterPath, QRegion
# ---- qdarktheme for modern dark/light mode ----
import qdarktheme

from config.config import TRANSLATIONS, SYSTEM, load_user_config, save_user_config, IS_MAC
from core.downloader import DownloaderEngine
from core.installer import DependencyInstaller
from utils import setup_env_path, open_download_folder, resolve_cookie_plugin_url
from .widgets import setup_styles, PasteFix


# --- Custom Frameless Title Bar (platform-aware) ---
class TitleBar(QWidget):
    """
    Lightweight, platform-aware title bar.
    Responsibilities:
    - Layout (traffic lights / title)
    - Visual style (hover, spacing)
    - Window drag forwarding
    """

    HEIGHT = 36
    BTN_SIZE = 12
    RADIUS = 6

    def __init__(self, parent):
        super().__init__(parent)
        self._parent = parent
        self._drag_pos = None
        self.is_mac = IS_MAC

        self.setFixedHeight(self.HEIGHT)
        self.setObjectName("TitleBar")
        self.setMouseTracking(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        # -------- macOS traffic lights (left) --------
        if self.is_mac:
            self._traffic = QWidget(self)
            self._traffic.setObjectName("MacTraffic")
            self._traffic.setFixedHeight(self.HEIGHT)

            traffic_layout = QHBoxLayout(self._traffic)
            traffic_layout.setContentsMargins(4, 0, 4, 0)
            traffic_layout.setSpacing(6)

            self.btn_close = self._make_mac_btn("#ff5f57")
            self.btn_min = self._make_mac_btn("#ffbd2e")
            self.btn_max = self._make_mac_btn("#28c840")

            # Delegate behavior to MainWindow (single source of truth)
            self.btn_close.clicked.connect(self._parent.close)
            self.btn_min.clicked.connect(self._parent.showMinimized)
            self.btn_max.clicked.connect(self._parent.showFullScreen)

            traffic_layout.addWidget(self.btn_close)
            traffic_layout.addWidget(self.btn_min)
            traffic_layout.addWidget(self.btn_max)
            layout.addWidget(self._traffic)

        # -------- title --------
        self.title_label = QLabel(parent.windowTitle(), self)
        self.title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.title_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.title_label.setObjectName("TitleLabel")
        layout.addWidget(self.title_label)
        layout.addStretch(1)

        # -------- Windows controls (right) --------
        if not self.is_mac:
            self.btn_min = QPushButton("–", self)
            self.btn_max = QPushButton("▢", self)
            self.btn_close = QPushButton("✕", self)

            for b in (self.btn_min, self.btn_max, self.btn_close):
                b.setFixedSize(32, 24)
                b.setFocusPolicy(Qt.NoFocus)

            self.btn_min.clicked.connect(self._parent.showMinimized)
            self.btn_max.clicked.connect(self._parent.toggle_maximize)
            self.btn_close.clicked.connect(self._parent.close)

            layout.addWidget(self.btn_min)
            layout.addWidget(self.btn_max)
            layout.addWidget(self.btn_close)

        self._apply_style()
        self.update_title_color()

    # -------- helpers --------

    def _make_mac_btn(self, color: str) -> QPushButton:
        btn = QPushButton(self)
        btn.setFixedSize(self.BTN_SIZE, self.BTN_SIZE)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setCursor(Qt.ArrowCursor)
        btn.setObjectName("MacTrafficButton")
        btn.setStyleSheet(
            f"background:{color}; border-radius:{self.RADIUS}px;"
        )
        return btn

    def _apply_style(self):
        """
        Purely visual. No behavior here.
        """
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(QPalette.Window, pal.color(QPalette.Window))
        self.setPalette(pal)

        self.setStyleSheet(
            """
            QWidget#TitleBar {
                background-color: palette(window);
            }

            QLabel#TitleLabel {
                font-weight: 600;
                font-size: 13px;
            }

            QWidget#MacTraffic:hover {
                background-color: palette(alternate-base);
                border-radius: 8px;
            }

            QPushButton {
                background: transparent;
                color: palette(text);
            }
            """
        )

    # -------- public API --------

    def update_title(self, text: str):
        self.title_label.setText(text)

    def update_title_color(self):
        theme = getattr(self._parent, "theme", "dark")
        if theme == "dark":
            self.title_label.setStyleSheet(
                "color: rgba(255,255,255,0.85);"
            )
        else:
            self.title_label.setStyleSheet(
                "color: rgba(0,0,0,0.75);"
            )

    # -------- window drag --------

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and not self.childAt(event.pos()):
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self._parent.move(self._parent.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None


class MainWindow(QWidget):
    installer_finished_signal = Signal(bool)

    def _reset_download_ui(self):
        """Reset UI state after download finishes or is stopped (v6 behavior)."""
        t = self.get_current_trans()
        self.download_controller = None
        self.download_btn.setText(t["btn_start"])
        self.install_btn.setEnabled(True)
        self.btn_path.setEnabled(True)
        self.btn_sel_cookie.setEnabled(self.cookie_source == "file")

    log_signal = Signal(str, str)
    download_finished_signal = Signal(bool)

    def _os_supported_browsers(self):
        """v6multi semantics: which browser cookies make sense on this OS."""
        from config.config import IS_MAC, IS_WIN, IS_LINUX
        if IS_MAC:
            return {"safari", "chrome", "firefox"}
        elif IS_WIN:
            return {"chrome", "edge", "firefox"}
        elif IS_LINUX:
            return {"chrome", "firefox"}
        else:
            return {"chrome", "firefox"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # Use a consistent cross-platform Qt style
        try:
            from PySide6.QtWidgets import QApplication
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

        # cookie mode (v6multi compatible, OS-based default)
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

        # ---- core ----
        self.download_controller = None
        self.downloader = DownloaderEngine(
            self.log_thread_safe,
            translations=TRANSLATIONS,
            lang=self.lang,
        )

        # v6-style explicit wiring (safe even if __init__ signature changes)
        self.downloader.on_done = self.on_download_done

        self.installer = DependencyInstaller(
            self.log_thread_safe,
            translations=TRANSLATIONS,
            lang=self.lang,
        )

        # cache dependency availability (updated on startup)
        self._aria2_available = True

        self.threadpool = QThreadPool.globalInstance()

        # ---- ui ----
        self._build_ui()

        # ---- theme ----
        self.theme = self.config_data.get("theme", "dark")
        qdarktheme.setup_theme(self.theme)
        for w in (self, self._content, self.title_bar):
            w.style().unpolish(w)
            w.style().polish(w)
            w.update()
        self.update_config("theme", self.theme)
        # Ensure dark theme propagates to all widgets
        try:
            QApplication.setAttribute(Qt.AA_UseStyleSheetPropagationInWidgetStyles, True)
        except Exception:
            pass

        self.restore_config_state()
        self.check_deps_on_start()
        self.log_signal.connect(self._append_log)

        self.download_finished_signal.connect(self._handle_download_done)
        self.installer_finished_signal.connect(self._on_installer_finished)

        # Ensure download button state is correct on startup
        self._update_download_enabled()

    # ---------------- helpers ----------------
    def get_current_trans(self):
        return TRANSLATIONS.get(self.lang, TRANSLATIONS["en"])

    def _map_exception_to_user_message(self, exc: Exception) -> str:
        """Translate core exceptions into user-friendly messages based on current UI language."""
        text = str(exc).lower()
        is_zh = self.lang == "zh"

        # RE engine input errors
        if "re engine only supports" in text or "m3u8" in text:
            return (
                "RE 引擎需要直接的 m3u8/mpd 链接，请对网页链接使用 yt-dlp。"
                if is_zh
                else "RE engine requires a direct m3u8/mpd URL. Please use yt-dlp."
            )

        # Dependency-related errors
        if "not found" in text or "missing" in text:
            return (
                "缺少必要的依赖，请点击『修复依赖』。"
                if is_zh
                else "Required dependency not found. Please run Fix Dependencies."
            )

        # User cancellation or stop
        if "stopped" in text or "cancel" in text:
            return (
                "下载已停止。"
                if is_zh
                else "Download stopped."
            )

        # Fallback
        return (
            "发生错误，请查看上方日志。"
            if is_zh
            else "An error occurred. Please check the log above."
        )

    def update_config(self, key, value):
        self.config_data[key] = value
        save_user_config(self.config_data)

    def _update_download_enabled(self):
        is_windows = self.system == "Windows"
        using_browser_cookie = self.cookie_source in {"chrome", "edge", "firefox", "safari"}
        using_local_file = self.cookie_source == "file"
        local_file_missing = using_local_file and not self.cookie_file_path

        # Case 1: Windows + browser cookie (unsupported)
        if is_windows and using_browser_cookie:
            self.download_btn.setEnabled(False)
            t = self.get_current_trans()
            msg = t.get(
                "log_win_browser_cookie_unsupported",
                "Browser cookies are not supported on Windows. Please use Local Cookie File."
            )
            if not getattr(self, "_win_cookie_warned", False):
                self._win_cookie_warned = True
                self.log_thread_safe(msg + "\n", "warning")
            return

        # Case 2: Local cookie file selected but no file chosen
        if local_file_missing:
            self.download_btn.setEnabled(False)
            t = self.get_current_trans()
            msg = t.get(
                "log_local_cookie_missing",
                "Local cookie file selected but no file chosen."
            )
            if not getattr(self, "_local_cookie_warned", False):
                self._local_cookie_warned = True
                self.log_thread_safe(msg + "\n", "warning")
            return

        # Otherwise: enable download
        self.download_btn.setEnabled(True)
        self._win_cookie_warned = False
        self._local_cookie_warned = False

    def log_thread_safe(self, text, tag=None):
        self.log_signal.emit(text, tag or "info")

    @Slot(str, str)
    def _append_log(self, text, tag):
        prefix = {"error": "❌ ", "success": "✅ ", "warning": "⚠️ "}.get(tag, "")
        self.log_text.appendPlainText(prefix + text)
        self.log_text.setMaximumBlockCount(1000)

    # ---------------- UI ----------------
    def _build_ui(self):
        t = self.get_current_trans()
        display_name = "macOS" if self.system == "Darwin" else self.system
        self.setWindowTitle(f"{t['title']} ({display_name})")
        self.resize(740, 820 if self.system == "Darwin" else 780)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # real content container for translucent window
        self._content = QWidget(self)
        self._content.setObjectName("MainWindowRoot")
        self._content.setAutoFillBackground(True)
        pal = self._content.palette()
        pal.setColor(self._content.backgroundRole(), pal.color(QPalette.Base))
        self._content.setPalette(pal)
        # --- macOS/Qt native rounded corners: only style content, not window ---
        self._content.setAttribute(Qt.WA_StyledBackground, True)
        self._content.setStyleSheet("""
QWidget#MainWindowRoot {
    border-radius: 12px;
}
""")

        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)

        root.addWidget(self._content)
        # Custom title bar
        self.title_bar = TitleBar(self)
        content_layout.addWidget(self.title_bar)
        # Remove default margins to avoid white bands in dark mode
        # (already set above)

        # top bar
        top = QHBoxLayout()
        self.btn_open = QPushButton(t["btn_open_dir"])
        self.btn_open.setFixedWidth(120)
        self.btn_open.clicked.connect(lambda: open_download_folder(self.download_dir))
        top.addWidget(self.btn_open)

        self.btn_clear = QPushButton(t["btn_clear_log"])
        self.btn_clear.setFixedWidth(110)
        self.btn_clear.clicked.connect(lambda: self.log_text.clear())
        top.addWidget(self.btn_clear)

        top.addStretch()

        # language selector
        self.lang_combo = ThemedComboBox()
        self.lang_combo.setFont(self.font_ui)
        self.lang_combo.addItems(["English", "中文"])
        self.lang_combo.setCurrentIndex(0 if self.lang == "en" else 1)
        self.lang_combo.currentIndexChanged.connect(self.change_language)
        top.addWidget(QLabel("🌐"))
        top.addWidget(self.lang_combo)

        # theme selector (dark / light)
        self.theme_combo = ThemedComboBox()
        self.lang_combo.setFont(self.font_ui)
        self.theme_combo.addItems(["Dark", "Light"])
        self.theme_combo.setCurrentIndex(0 if self.theme == "dark" else 1)
        self.theme_combo.currentIndexChanged.connect(self.change_theme)
        top.addWidget(QLabel("🎨"))
        top.addWidget(self.theme_combo)

        # --- ComboBox sizing (language & theme) ---
        self.lang_combo.setFixedWidth(110)
        self.theme_combo.setFixedWidth(100)
        # Minimum height already set above

        # Normalize ComboBox sizing policy (prevent upward popup)
        self.lang_combo.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)
        self.theme_combo.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)

        self.install_btn = QPushButton(t["btn_fix_dep"])
        self.install_btn.setFixedWidth(150)
        self.install_btn.clicked.connect(self.run_install)
        top.addWidget(self.install_btn)

        content_layout.addLayout(top)

        # url
        self.url_group = QGroupBox(t["frame_url"])
        v = QVBoxLayout(self.url_group)
        self.url_entry = QLineEdit()
        PasteFix(self.url_entry, self.cmd_key)
        v.addWidget(self.url_entry)
        content_layout.addWidget(self.url_group)

        # tools
        self.tools_group = QGroupBox(t["frame_tools"])
        tv = QVBoxLayout(self.tools_group)
        hl = QHBoxLayout()
        # cookie mode radios (v6multi)
        self.rb_guest = QRadioButton(t["mode_guest"])
        self.rb_chrome = QRadioButton("Chrome")
        self.rb_edge = QRadioButton("Edge")
        self.rb_firefox = QRadioButton("Firefox")
        self.rb_safari = QRadioButton("Safari")
        self.rb_file = QRadioButton(t["mode_local_file"])

        for rb in [self.rb_guest, self.rb_chrome, self.rb_edge, self.rb_firefox, self.rb_safari, self.rb_file]:
            hl.addWidget(rb)

        # Enforce exclusive radios (Qt fix, Tk semantics)
        from PySide6.QtWidgets import QButtonGroup
        self.cookie_group = QButtonGroup(self)
        for rb in [self.rb_guest, self.rb_chrome, self.rb_edge, self.rb_firefox, self.rb_safari, self.rb_file]:
            self.cookie_group.addButton(rb)

        # default selection (v6multi exact)
        cookie_map = {
            "none": self.rb_guest,
            "chrome": self.rb_chrome,
            "edge": self.rb_edge,
            "firefox": self.rb_firefox,
            "safari": self.rb_safari,
            "file": self.rb_file,
        }
        # hide browsers not supported on this OS (v6multi)
        supported = self._os_supported_browsers()
        if "chrome" not in supported:
            self.rb_chrome.hide()
        if "edge" not in supported:
            self.rb_edge.hide()
        if "firefox" not in supported:
            self.rb_firefox.hide()
        if "safari" not in supported:
            self.rb_safari.hide()

        # sanitize cookie_source if unsupported
        if self.cookie_source not in supported and self.cookie_source not in {"file", "none"}:
            self.cookie_source = "none"

        cookie_map.get(self.cookie_source, self.rb_guest).setChecked(True)

        # cookie file select
        self.btn_sel_cookie = QPushButton(t["btn_select"])
        self.btn_sel_cookie.clicked.connect(self.select_cookie_file)
        hl.addWidget(self.btn_sel_cookie)

        # local file label (below file picker, v6multi)
        self.file_label = QLabel(t["status_no_file"])
        self.file_label.setStyleSheet("color:#888")
        hl.addWidget(self.file_label)

        tv.addLayout(hl)

        # cookie & m3u8 helpers (v6multi features)
        helper_layout = QHBoxLayout()

        # 1) cookies.txt exporter (for RE)
        self.btn_cookie_plugin = QPushButton(
            t.get("btn_cookie_export", "Get cookies.txt")
        )
        self.btn_cookie_plugin.setFixedWidth(160)
        self.btn_cookie_plugin.clicked.connect(self.open_cookie_plugin)
        helper_layout.addWidget(self.btn_cookie_plugin)

        # 2) CatCatch (m3u8 capture)
        self.btn_catcatch = QPushButton(
            t.get("btn_catcatch", "Get m3u8 (CatCatch)")
        )
        self.btn_catcatch.setFixedWidth(160)
        self.btn_catcatch.clicked.connect(self.open_catcatch)
        helper_layout.addWidget(self.btn_catcatch)

        helper_layout.addStretch()
        tv.addLayout(helper_layout)

        content_layout.addWidget(self.tools_group)

        # Windows: slightly increase button font size for better readability
        if self.system == "Windows":
            for btn in self.findChildren(QPushButton):
                btn.setStyleSheet(
                    btn.styleSheet() + " QPushButton { font-size: 13px; }"
                )

        # controls
        ctrl = QHBoxLayout()
        ev = QVBoxLayout()
        self.lbl_engine = QLabel(t["label_engine"])
        ev.addWidget(self.lbl_engine)
        self.engine_combo = ThemedComboBox()
        self.engine_combo.setFont(self.font_ui)
        self.engine_combo.addItems([t["engine_native"], t["engine_aria2"], t["engine_re"]])
        self.engine_combo.currentIndexChanged.connect(self.toggle_engine_ui)
        self.engine_combo.setFont(self.font_ui)
        self.engine_combo.setMinimumHeight(28)
        ev.addWidget(self.engine_combo)

        # Normalize ComboBox sizing policy (prevent upward popup)
        self.engine_combo.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)

        th = QHBoxLayout()
        self.lbl_threads = QLabel(t.get("label_threads", "Threads:"))
        th.addWidget(self.lbl_threads)
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 64)
        self.thread_spin.setValue(8)
        self.thread_spin.setEnabled(False)
        th.addWidget(self.thread_spin)
        ev.addLayout(th)
        ctrl.addLayout(ev)

        pv = QVBoxLayout()
        ph = QHBoxLayout()
        self.lbl_save_path = QLabel(t["label_save_path"])
        ph.addWidget(self.lbl_save_path)
        self.path_label = QLabel(self.download_dir[-30:])
        self.path_label.setStyleSheet("color:#007AFF")
        ph.addWidget(self.path_label)
        ph.insertStretch(0, 1)
        pv.addLayout(ph)
        self.btn_path = QPushButton(t["btn_change_path"])
        self.btn_path.setFixedWidth(110)
        self.btn_path.clicked.connect(self.change_download_path)
        pv.addWidget(self.btn_path, alignment=Qt.AlignRight)
        ctrl.addLayout(pv)
        content_layout.addLayout(ctrl)

        # start
        self.download_btn = QPushButton(t["btn_start"])
        self.download_btn.setFixedWidth(280)
        self.download_btn.clicked.connect(self.toggle_download)
        content_layout.addWidget(self.download_btn, alignment=Qt.AlignHCenter)

        # log
        self.lbl_log = QLabel(t["label_log"])
        content_layout.addWidget(self.lbl_log)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        content_layout.addWidget(self.log_text)

        for src, rb in {
            "none": self.rb_guest,
            "chrome": self.rb_chrome,
            "edge": self.rb_edge,
            "firefox": self.rb_firefox,
            "safari": self.rb_safari,
            "file": self.rb_file,
        }.items():
            rb.toggled.connect(lambda checked, s=src: checked and self._set_cookie_source(s))

        # file picker enabled only in file mode (startup safety)
        self.btn_sel_cookie.setEnabled(self.cookie_source == "file")

    # ---------------- logic ----------------
    def _set_cookie_source(self, source: str):
        # v6multi-compatible cookie state machine
        self.cookie_source = source
        self.update_config("cookie_source", source)

        # file picker only enabled in file mode
        self.btn_sel_cookie.setEnabled(source == "file")

        # update file label when leaving file mode
        if source != "file" and not self.cookie_file_path:
            self.file_label.setText(self.get_current_trans()["status_no_file"])

        # logging (exact v6multi semantics)
        t = self.get_current_trans()
        if source == "none":
            self.log_thread_safe(t.get("log_warning_guest", "Warning: Guest mode"), "warning")
        elif source == "file":
            self.log_thread_safe(t.get("log_mode_file", "Mode: Cookie file"), "info")
        else:
            self.log_thread_safe(
                t.get("log_mode_browser", "Mode: {} Cookie").format(source.capitalize()),
                "info",
            )
        self._update_download_enabled()

    def toggle_engine_ui(self):
        is_re = self.engine_combo.currentIndex() == 2

        # RE DOES support thread-count; keep enabled for all engines
        self.thread_spin.setEnabled(True)

        # v6multi rule: RE does not support browser cookies -> grey out browser cookie radios
        for src, rb in {
            "chrome": self.rb_chrome,
            "edge": self.rb_edge,
            "firefox": self.rb_firefox,
            "safari": self.rb_safari,
        }.items():
            if rb.isVisible():
                rb.setEnabled(not is_re)

        # if currently on browser cookie and switched to RE, fall back to guest
        if is_re and self.cookie_source in {"chrome", "edge", "firefox", "safari"}:
            self.rb_guest.setChecked(True)

    def toggle_download(self):
        t = self.get_current_trans()
        if self.download_controller and self.download_controller._proc:
            # v6 behavior: reset UI immediately, then stop process asynchronously
            self.log_thread_safe(t.get("log_download_stop", "\n>>> Download Stopped.\n"), "warning")
            controller = self.download_controller
            self._reset_download_ui()
            try:
                controller.stop()
            except Exception:
                pass
            return

        url = self.url_entry.text().strip()
        if not url:
            # Log-only hint (no modal dialog)
            msg = t.get("msg_input_url", "Please enter a URL")
            self.log_thread_safe(msg + "\n", "warning")
            return

        # Pre-check: RE engine requires a direct m3u8/mpd URL (log-only, no modal)
        engine_text = self.engine_combo.currentText().lower()
        is_re = ("re" in engine_text)
        if is_re:
            ul = url.lower()
            if not (ul.endswith('.m3u8') or ul.endswith('.mpd') or 'm3u8' in ul):
                msg = t.get(
                    "log_re_requires_m3u8",
                    "RE engine requires a direct m3u8/mpd URL. Please use yt-dlp for webpage URLs."
                )
                self.log_thread_safe(msg + "\n", "warning")
                return

        self.log_text.clear()
        self.download_btn.setText(t["btn_stop"])

        opts = {
            "engine": ["native", "aria2", "re"][self.engine_combo.currentIndex()],
            "download_dir": self.download_dir,
            "threads": self.thread_spin.value(),
            "cookie_source": self.cookie_source,
            "cookie_path": self.cookie_file_path,
        }

        try:
            self.download_controller = self.downloader.run_threaded(url, opts)
        except Exception as e:
            msg = self._map_exception_to_user_message(e)
            self.log_thread_safe(msg + "\n", "error")
            self.download_btn.setText(t["btn_start"])
            self.download_controller = None
            return

        self.install_btn.setEnabled(False)
        self.btn_path.setEnabled(False)
        self.btn_sel_cookie.setEnabled(False)

    def on_download_done(self, success, rc=None):
        self.download_finished_signal.emit(bool(success))

    def _handle_download_done(self, success):
        # v6 semantics: always reset UI on completion
        # Result logging is handled by downloader (avoid duplicate logs)
        self._reset_download_ui()

    def run_install(self):
        t = self.get_current_trans()
        # disable install UI immediately
        self.install_btn.setEnabled(False)
        self.install_btn.setText(t.get("btn_fix_dep_running", "Fixing..."))

        # start installer in its own thread-safe controller
        controller = self.installer.install_all_threaded()

        # watcher runs in a plain Python thread (not a Qt worker) and notifies UI on main thread
        def watcher():
            success = True
            try:
                # wait for the install thread to finish, if available
                th = getattr(controller, "_thread", None)
                if th is not None:
                    th.join()
                else:
                    # fallback: if controller exposes is_alive use that loop
                    is_alive = getattr(controller, "is_alive", None)
                    if callable(is_alive):
                        while is_alive():
                            threading.Event().wait(0.2)
            except Exception:
                success = False
            # emit back to main thread to update UI
            self.installer_finished_signal.emit(success)

        threading.Thread(target=watcher, daemon=True).start()

    @Slot(bool)
    def _on_installer_finished(self, success: bool):
        t = self.get_current_trans()
        if success:
            self.log_thread_safe(t.get("msg_fix_done", "Finished"), "success")
        else:
            self.log_thread_safe(t.get("msg_fix_failed", "Dependency installation finished with errors"), "warning")
        self.install_btn.setEnabled(True)
        self.install_btn.setText(t["btn_fix_dep"])

    def check_deps_on_start(self):
        def task():
            try:
                status = self.installer.check_status()
                t = self.get_current_trans()

                if not status.get("yt-dlp"):
                    self.log_thread_safe(t.get("log_check_yt_fail", "yt-dlp not found"), "warning")

                if not status.get("ffmpeg"):
                    self.log_thread_safe(t.get("log_check_re_warning", "ffmpeg not found"), "warning")

                # macOS: aria2 is optional; hide engine if unavailable
                if IS_MAC and not status.get("aria2"):
                    self._aria2_available = False

                    def hide_aria2():
                        # aria2 is at index 1: [native, aria2, re]
                        if self.engine_combo.count() >= 3:
                            self.engine_combo.removeItem(1)

                    QTimer.singleShot(0, hide_aria2)
                else:
                    self._aria2_available = True

            except Exception:
                pass

        self.threadpool.start(task)

    def change_language(self):
        new_lang = "zh" if self.lang_combo.currentText() == "中文" else "en"
        if new_lang == self.lang:
            return
        self.lang = new_lang
        self.update_config("lang", self.lang)

        # propagate language to core modules
        try:
            self.downloader.set_language(self.lang)
            self.installer.set_language(self.lang)
        except Exception:
            pass

        # refresh visible texts only (do NOT rebuild layout)
        self._refresh_text()

    def _refresh_text(self):
        """Refresh all visible texts (v6multi-compatible, no layout rebuild)."""
        t = self.get_current_trans()
        display_name = "macOS" if self.system == "Darwin" else self.system

        # window title
        self.setWindowTitle(f"{t['title']} ({display_name})")
        if hasattr(self, 'title_bar'):
            self.title_bar.update_title(self.windowTitle())

        # top bar
        self.btn_open.setText(t["btn_open_dir"])
        self.btn_clear.setText(t["btn_clear_log"])
        self.install_btn.setText(t["btn_fix_dep"])

        # language combo (silent)
        self.lang_combo.blockSignals(True)
        self.lang_combo.setCurrentIndex(0 if self.lang == "en" else 1)
        self.lang_combo.blockSignals(False)

        # group boxes
        self.url_group.setTitle(t["frame_url"])
        self.tools_group.setTitle(t["frame_tools"])

        # cookie / local file
        self.rb_guest.setText(t["mode_guest"])
        self.rb_file.setText(t["mode_local_file"])
        self.btn_sel_cookie.setText(t["btn_select"])
        if not self.cookie_file_path:
            self.file_label.setText(t["status_no_file"])

        # cookie plugin button text and catcatch
        if hasattr(self, "btn_cookie_plugin"):
            self.btn_cookie_plugin.setText(
                t.get("btn_cookie_export", "Get cookies.txt")
            )
        if hasattr(self, "btn_catcatch"):
            self.btn_catcatch.setText(
                t.get("btn_catcatch", "Get m3u8 (CatCatch)")
            )

        # engine / threads
        self.lbl_engine.setText(t["label_engine"])
        self.lbl_threads.setText(t.get("label_threads", "Threads:"))

        self.engine_combo.blockSignals(True)
        current_index = self.engine_combo.currentIndex()
        # Re-check aria2 availability to avoid stale UI state

        aria2_available = True
        try:
            status = self.installer.check_status()
            aria2_available = bool(status.get("aria2"))
        except Exception:
            aria2_available = getattr(self, "_aria2_available", True)

        self._aria2_available = aria2_available

        self.engine_combo.clear()
        engines = [t["engine_native"]]
        if aria2_available:
            engines.append(t["engine_aria2"])
        engines.append(t["engine_re"])
        self.engine_combo.addItems(engines)

        self.engine_combo.setCurrentIndex(current_index)
        self.engine_combo.blockSignals(False)

        # save path
        self.lbl_save_path.setText(t["label_save_path"])
        self.btn_path.setText(t["btn_change_path"])
        self.path_label.setText(self.download_dir[-30:])

        # log area
        self.lbl_log.setText(t["label_log"])

        # optional info
        # log language switch once per change (avoid spam)
        if getattr(self, "_last_lang_logged", None) != self.lang:
            self._last_lang_logged = self.lang
            try:
                msg = t.get("log_language_switched")
                if not msg:
                    msg = ">>> Language switched to {}\n"
                self.log_thread_safe(msg.format(self.lang), "info")
            except Exception:
                pass

        # re-apply RE cookie disable after language refresh
        is_re = self.engine_combo.currentIndex() == 2
        for rb in [self.rb_chrome, self.rb_edge, self.rb_firefox, self.rb_safari]:
            if rb.isVisible():
                rb.setEnabled(not is_re)

        # keep download button state consistent
        if self.download_controller and self.download_controller._proc:
            self.download_btn.setText(t["btn_stop"])
        else:
            self.download_btn.setText(t["btn_start"])

        # Update download button enabled state after language refresh
        self._update_download_enabled()

    def select_cookie_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select cookie file", os.path.expanduser("~"), "Text Files (*.txt)")
        if f:
            self.cookie_file_path = f
            self.file_label.setText(os.path.basename(f))
            self.update_config("cookie_path", f)
        self._update_download_enabled()

    def change_download_path(self):
        d = QFileDialog.getExistingDirectory(self, "Select download folder", self.download_dir)
        if d:
            self.download_dir = d
            self.path_label.setText(d[-30:])
            self.update_config("download_dir", d)

    def restore_config_state(self):
        """Restore UI state from saved config (cookie file, etc.)."""
        t = self.get_current_trans()
        if self.cookie_file_path and os.path.exists(self.cookie_file_path):
            # show loaded cookie file name
            self.file_label.setText(os.path.basename(self.cookie_file_path))
            self.file_label.setStyleSheet("color:#007AFF")
            # optional log
            try:
                self.log_thread_safe(t.get("log_load_cookie_ok", "Loaded previous cookie file."), "success")
            except Exception:
                pass

    def open_cookie_plugin(self):
        """
        Open cookies.txt exporter for RE workflow.
        """
        import webbrowser

        url = resolve_cookie_plugin_url(
            browser=self.cookie_source,
            system=self.system,
            prefer="cookies_txt",
        )

        if not url:
            self.log_thread_safe("No suitable cookies.txt exporter found for this browser.\n", "warning")
            return

        webbrowser.open(url)

    # CatCatch is for capturing m3u8 URLs, NOT cookies
    def open_catcatch(self):
        """
        Open CatCatch plugin page for capturing m3u8 URLs.
        Independent from cookie export.
        """
        import webbrowser

        url = resolve_cookie_plugin_url(
            browser=self.cookie_source,
            system=self.system,
            prefer="catcatch",
        )

        if not url:
            self.log_thread_safe("CatCatch is not available for this browser.\n", "warning")
            return

        webbrowser.open(url)

    def change_theme(self):
        new_theme = "dark" if self.theme_combo.currentText() == "Dark" else "light"
        if new_theme == self.theme:
            return

        self.theme = new_theme
        qdarktheme.setup_theme(self.theme)
        pal = self._content.palette()
        pal.setColor(self._content.backgroundRole(), pal.color(QPalette.Base))
        if hasattr(self, "title_bar"):
            self.title_bar.update_title_color()
        self._content.setPalette(pal)
        self._content.update()
        widgets_to_refresh = [self, self._content, self.lang_combo, self.theme_combo, self.engine_combo]
        for w in widgets_to_refresh:
            w.style().unpolish(w)
            w.style().polish(w)
            w.update()
        self.update_config("theme", self.theme)
        self._refresh_text()

        # optional log
        t = self.get_current_trans()
        msg = t.get("log_theme_switched", "Theme switched to {}.")
        self.log_thread_safe(msg.format(self.theme), "info")


class ThemedComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置光标为手型，增加交互感
        self.setCursor(Qt.PointingHandCursor)
        # 允许调整大小以适应内容，但保持最小高度
        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.setMinimumHeight(30)  # 稍微增高一点，更现代

        # 设置视图（下拉列表）的样式代理，使其支持圆角
        view = self.view()
        view.window().setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        view.setAttribute(Qt.WA_TranslucentBackground)

        # 应用样式
        self._apply_styles()

    def _apply_styles(self):
        """
        使用 palette() 引用全局配色，这样 qdarktheme 切换时会自动生效。
        """
        self.setStyleSheet("""
        /* 主体样式 */
        QComboBox {
            background-color: palette(base);
            color: palette(text);
            border: 1px solid palette(mid);
            border-radius: 6px;
            padding: 4px 10px;
            /* 字体大小继承自父级，也可以在这里微调，例如 font-size: 13px; */
        }

        /* 鼠标悬停 */
        QComboBox:hover {
            border: 1px solid palette(highlight);
            background-color: palette(alternate-base);
        }

        /* 获得焦点（按下） */
        QComboBox:on { 
            border: 1px solid palette(highlight);
        }

        /* 下拉箭头区域 */
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
            border-left-width: 0px;
        }

        /* 下拉箭头图标 (使用透明边框绘制简单的箭头，或者依赖默认) */
        QComboBox::down-arrow {
            width: 0; 
            height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid palette(text); /* 箭头颜色跟随文字 */
            margin-right: 6px;
        }

        /* 下拉列表 (Popup) 样式 */
        QComboBox QAbstractItemView {
            background-color: palette(base);
            color: palette(text);
            border: 1px solid palette(mid);
            border-radius: 6px;
            outline: none; /* 去掉选中时的虚线框 */
            padding: 4px;
            selection-background-color: palette(highlight);
            selection-color: palette(highlighted-text);
        }

        /* 下拉列表项 */
        QComboBox QAbstractItemView::item {
            min-height: 24px;
            border-radius: 4px; /* 列表项也搞圆角 */
            padding-left: 5px;
        }

        QComboBox QAbstractItemView::item:hover {
            background-color: palette(midlight);
        }

        QComboBox QAbstractItemView::item:selected {
            background-color: palette(highlight);
            color: palette(highlighted-text);
        }
        """)