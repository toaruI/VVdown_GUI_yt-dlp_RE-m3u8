# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QGroupBox, QRadioButton, QPlainTextEdit,
    QSpinBox, QButtonGroup
)

from .widgets import PasteFix, ThemedComboBox
from .title_bar import TitleBar


class MainWindowUI:
    """UI builder class for MainWindow."""

    def setup_ui(self, mw):
        t = mw.get_current_trans()
        display_name = "macOS" if mw.system == "Darwin" else mw.system
        mw.setWindowTitle(f"{t['title']} ({display_name})")
        size = mw.DEFAULT_WINDOW_SIZE_MAC if mw.system == "Darwin" else mw.DEFAULT_WINDOW_SIZE
        mw.resize(*size)
        mw.setMinimumSize(*mw.MIN_WINDOW_SIZE)

        self._setup_root_layout(mw)
        self._setup_title_bar(mw)
        self._setup_top_bar(mw, t)
        self._setup_url_section(mw, t)
        self._setup_cookie_section(mw, t)
        self._setup_helper_buttons(mw, t)
        self._apply_windows_font_fix(mw)
        self._setup_engine_controls(mw, t)
        self._setup_download_button(mw, t)
        self._setup_log_section(mw, t)
        self._connect_cookie_signals(mw)

    # ================================================================
    # Root Layout
    # ================================================================

    def _setup_root_layout(self, mw):
        root = QVBoxLayout(mw)
        root.setContentsMargins(*mw.NORMAL_MARGINS)

        mw._content = QWidget(mw)
        mw._content.setObjectName("MainWindowRoot")
        mw._content.setAutoFillBackground(False)
        mw._content.setAttribute(Qt.WA_StyledBackground, True)

        self._content_layout = QVBoxLayout(mw._content)
        self._content_layout.setContentsMargins(10, 6, 10, 10)
        self._content_layout.setSpacing(8)

        root.addWidget(mw._content)

    # ================================================================
    # Title Bar
    # ================================================================

    def _setup_title_bar(self, mw):
        mw.title_bar = TitleBar(mw)
        self._content_layout.addWidget(mw.title_bar)

    # ================================================================
    # Top Bar: Open Dir / Clear Log / Language / Theme / Fix Deps
    # ================================================================

    def _setup_top_bar(self, mw, t):
        top = QHBoxLayout()

        mw.btn_open = QPushButton(t["btn_open_dir"])
        mw.btn_open.setMinimumWidth(120)
        mw.btn_open.clicked.connect(mw._open_download_folder)
        top.addWidget(mw.btn_open)

        mw.btn_clear = QPushButton(t["btn_clear_log"])
        mw.btn_clear.setMinimumWidth(100)
        mw.btn_open.clicked.connect(mw._open_download_folder)
        top.addWidget(mw.btn_clear)

        top.addStretch()

        # ---- Language selector ----
        mw.lang_combo = ThemedComboBox()
        mw.lang_combo.setFont(mw.font_ui)
        mw.lang_combo.addItems(["English", "中文"])
        mw.lang_combo.setCurrentIndex(0 if mw.lang == "en" else 1)
        mw.lang_combo.setFixedWidth(110)
        mw.lang_combo.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)
        mw.lang_combo.currentIndexChanged.connect(mw.change_language)
        top.addWidget(QLabel("🌐"))
        top.addWidget(mw.lang_combo)

        # ---- Theme selector ----
        mw.theme_combo = ThemedComboBox()
        mw.theme_combo.setFont(mw.font_ui)
        mw.theme_combo.addItems(["Auto", "Dark", "Light"])
        theme_index = {"auto": 0, "dark": 1, "light": 2}.get(mw.theme, 1)
        mw.theme_combo.setCurrentIndex(theme_index)
        mw.theme_combo.setFixedWidth(100)
        mw.theme_combo.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)
        mw.theme_combo.currentIndexChanged.connect(mw.change_theme)
        top.addWidget(QLabel("🎨"))
        top.addWidget(mw.theme_combo)

        # ---- Fix dependencies ----
        mw.install_btn = QPushButton(t["btn_fix_dep"])
        mw.install_btn.setMinimumWidth(140)
        mw.install_btn.clicked.connect(mw.run_install)
        top.addWidget(mw.install_btn)

        self._content_layout.addLayout(top)

    # ================================================================
    # URL Input
    # ================================================================

    def _setup_url_section(self, mw, t):
        mw.url_group = QGroupBox(t["frame_url"])
        v = QVBoxLayout(mw.url_group)
        mw.url_entry = QLineEdit()
        PasteFix(mw.url_entry, mw.cmd_key)
        v.addWidget(mw.url_entry)
        self._content_layout.addWidget(mw.url_group)

    # ================================================================
    # Cookie Mode Selection
    # ================================================================

    def _setup_cookie_section(self, mw, t):
        mw.tools_group = QGroupBox(t["frame_tools"])
        self._tools_layout = QVBoxLayout(mw.tools_group)

        hl = QHBoxLayout()

        # ---- Radio buttons ----
        mw.rb_guest = QRadioButton(t["mode_guest"])
        mw.rb_chrome = QRadioButton("Chrome")
        mw.rb_edge = QRadioButton("Edge")
        mw.rb_firefox = QRadioButton("Firefox")
        mw.rb_safari = QRadioButton("Safari")
        mw.rb_file = QRadioButton(t["mode_local_file"])

        all_radios = [
            mw.rb_guest, mw.rb_chrome, mw.rb_edge,
            mw.rb_firefox, mw.rb_safari, mw.rb_file,
        ]

        mw.cookie_group = QButtonGroup(mw)
        for rb in all_radios:
            hl.addWidget(rb)
            mw.cookie_group.addButton(rb)

        # ---- Hide unsupported browsers ----
        browser_radios = {
            "chrome": mw.rb_chrome,
            "edge": mw.rb_edge,
            "firefox": mw.rb_firefox,
            "safari": mw.rb_safari,
        }
        supported = mw._os_supported_browsers()
        for name, rb in browser_radios.items():
            if name not in supported:
                rb.hide()

        # ---- Sanitize cookie_source ----
        if mw.cookie_source not in supported and mw.cookie_source not in {"file", "none"}:
            mw.cookie_source = "none"

        # ---- Default selection ----
        source_map = {
            "none": mw.rb_guest, "chrome": mw.rb_chrome,
            "edge": mw.rb_edge, "firefox": mw.rb_firefox,
            "safari": mw.rb_safari, "file": mw.rb_file,
        }
        source_map.get(mw.cookie_source, mw.rb_guest).setChecked(True)

        # ---- File picker ----
        mw.btn_sel_cookie = QPushButton(t["btn_select"])
        mw.btn_sel_cookie.clicked.connect(mw.select_cookie_file)
        mw.btn_sel_cookie.setEnabled(mw.cookie_source == "file")
        hl.addWidget(mw.btn_sel_cookie)

        mw.file_label = QLabel(t["status_no_file"])
        mw.file_label.setStyleSheet("color:#888")
        hl.addWidget(mw.file_label)

        self._tools_layout.addLayout(hl)
        self._content_layout.addWidget(mw.tools_group)

    # ================================================================
    # Helper Buttons: cookies.txt exporter / CatCatch
    # ================================================================

    def _setup_helper_buttons(self, mw, t):
        helper_layout = QHBoxLayout()

        mw.btn_cookie_plugin = QPushButton(
            t.get("btn_cookie_export", "Get cookies.txt")
        )
        mw.btn_cookie_plugin.setMinimumWidth(150)
        mw.btn_cookie_plugin.clicked.connect(mw.open_cookie_plugin)
        helper_layout.addWidget(mw.btn_cookie_plugin)

        mw.btn_catcatch = QPushButton(
            t.get("btn_catcatch", "Get m3u8 (CatCatch)")
        )
        mw.btn_catcatch.setMinimumWidth(150)
        mw.btn_catcatch.clicked.connect(mw.open_catcatch)
        helper_layout.addWidget(mw.btn_catcatch)

        helper_layout.addStretch()
        self._tools_layout.addLayout(helper_layout)

    # ================================================================
    # Windows: Increase button font size
    # ================================================================

    def _apply_windows_font_fix(self, mw):
        if mw.system != "Windows":
            return
        for btn in mw.findChildren(QPushButton):
            btn.setStyleSheet(
                btn.styleSheet() + " QPushButton { font-size: 13px; }"
            )

    # ================================================================
    # Engine / Threads / Save Path
    # ================================================================

    def _setup_engine_controls(self, mw, t):
        ctrl = QHBoxLayout()

        # ---- Engine + Threads (left side) ----
        ev = QVBoxLayout()

        mw.lbl_engine = QLabel(t["label_engine"])
        ev.addWidget(mw.lbl_engine)

        mw.engine_combo = ThemedComboBox()
        mw.engine_combo.setFont(mw.font_ui)
        mw.engine_combo.addItems([
            t["engine_native"], t["engine_aria2"], t["engine_re"]
        ])
        mw.engine_combo.setMinimumHeight(28)
        mw.engine_combo.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)
        mw.engine_combo.currentIndexChanged.connect(mw.toggle_engine_ui)
        ev.addWidget(mw.engine_combo)

        th = QHBoxLayout()
        mw.lbl_threads = QLabel(t.get("label_threads", "Threads:"))
        th.addWidget(mw.lbl_threads)
        mw.thread_spin = QSpinBox()
        mw.thread_spin.setRange(1, 64)
        mw.thread_spin.setValue(8)
        mw.thread_spin.setEnabled(False)
        th.addWidget(mw.thread_spin)
        ev.addLayout(th)

        ctrl.addLayout(ev)

        # ---- Save path (right side) ----
        pv = QVBoxLayout()

        ph = QHBoxLayout()
        mw.lbl_save_path = QLabel(t["label_save_path"])
        ph.addWidget(mw.lbl_save_path)
        mw.path_label = QLabel(mw._truncate_path(mw.download_dir))
        mw.path_label.setStyleSheet("color:#007AFF")
        ph.addWidget(mw.path_label)
        ph.insertStretch(0, 1)
        pv.addLayout(ph)

        mw.btn_path = QPushButton(t["btn_change_path"])
        mw.btn_path.setMinimumWidth(110)
        mw.btn_path.clicked.connect(mw.change_download_path)
        pv.addWidget(mw.btn_path, alignment=Qt.AlignRight)

        ctrl.addLayout(pv)

        self._content_layout.addLayout(ctrl)

    # ================================================================
    # Download Button
    # ================================================================

    def _setup_download_button(self, mw, t):
        mw.download_btn = QPushButton(t["btn_start"])
        mw.download_btn.setMinimumWidth(260)
        mw.download_btn.setMaximumWidth(340)
        mw.download_btn.clicked.connect(mw.toggle_download)
        self._content_layout.addWidget(
            mw.download_btn, alignment=Qt.AlignHCenter
        )

    # ================================================================
    # Log Area
    # ================================================================

    def _setup_log_section(self, mw, t):
        mw.lbl_log = QLabel(t["label_log"])
        self._content_layout.addWidget(mw.lbl_log)

        mw.log_text = QPlainTextEdit()
        mw.log_text.setReadOnly(True)
        mw.log_text.setMaximumBlockCount(mw.LOG_MAX_LINES)
        self._content_layout.addWidget(mw.log_text)

    # ================================================================
    # Cookie Radio Signal Connections
    # ================================================================

    def _connect_cookie_signals(self, mw):
        source_map = {
            "none": mw.rb_guest,
            "chrome": mw.rb_chrome,
            "edge": mw.rb_edge,
            "firefox": mw.rb_firefox,
            "safari": mw.rb_safari,
            "file": mw.rb_file,
        }
        for src, rb in source_map.items():
            rb.toggled.connect(
                lambda checked, s=src: checked and mw._set_cookie_source(s)
            )