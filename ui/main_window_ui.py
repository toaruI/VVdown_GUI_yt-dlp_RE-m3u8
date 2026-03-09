# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QGroupBox, QRadioButton, QPlainTextEdit,
    QSpinBox, QButtonGroup
)

from utils import open_download_folder
from .title_bar import TitleBar
from .widgets import PasteFix, ThemedComboBox


class MainWindowUI:
    """UI builder class for MainWindow."""

    def setup_ui(self, main_window):
        t = main_window.get_current_trans()
        display_name = "macOS" if main_window.system == "Darwin" else main_window.system
        main_window.setWindowTitle(f"{t['title']} ({display_name})")
        main_window.resize(740, 820 if main_window.system == "Darwin" else 780)

        main_window.setMinimumSize(720, 600)

        root = QVBoxLayout(main_window)
        # Margin around content allows shadow to render
        root.setContentsMargins(*main_window.NORMAL_MARGINS)

        # real content container for translucent window
        main_window._content = QWidget(main_window)
        main_window._content.setObjectName("MainWindowRoot")
        main_window._content.setAutoFillBackground(False)
        main_window._content.setAttribute(Qt.WA_StyledBackground, True)

        content_layout = QVBoxLayout(main_window._content)
        content_layout.setContentsMargins(10, 6, 10, 10)
        content_layout.setSpacing(8)

        root.addWidget(main_window._content)
        # Custom title bar
        main_window.title_bar = TitleBar(main_window)
        content_layout.addWidget(main_window.title_bar)
        # Remove default margins to avoid white bands in dark mode
        # (already set above)

        # top bar
        top = QHBoxLayout()
        main_window.btn_open = QPushButton(t["btn_open_dir"])
        main_window.btn_open.setMinimumWidth(120)
        main_window.btn_open.clicked.connect(lambda: open_download_folder(main_window.download_dir))
        top.addWidget(main_window.btn_open)

        main_window.btn_clear = QPushButton(t["btn_clear_log"])
        main_window.btn_clear.setMinimumWidth(100)
        main_window.btn_clear.clicked.connect(lambda: main_window.log_text.clear())
        top.addWidget(main_window.btn_clear)

        top.addStretch()

        # language selector
        main_window.lang_combo = ThemedComboBox()
        main_window.lang_combo.setFont(main_window.font_ui)
        main_window.lang_combo.addItems(["English", "中文"])
        main_window.lang_combo.setCurrentIndex(0 if main_window.lang == "en" else 1)
        main_window.lang_combo.currentIndexChanged.connect(main_window.change_language)
        top.addWidget(QLabel("🌐"))
        top.addWidget(main_window.lang_combo)

        # theme selector (dark / light)
        main_window.theme_combo = ThemedComboBox()
        main_window.theme_combo.setFont(main_window.font_ui)
        main_window.theme_combo.addItems(["Auto", "Dark", "Light"])
        if main_window.theme == "auto":
            main_window.theme_combo.setCurrentIndex(0)
        elif main_window.theme == "dark":
            main_window.theme_combo.setCurrentIndex(1)
        else:  # light
            main_window.theme_combo.setCurrentIndex(2)
        main_window.theme_combo.currentIndexChanged.connect(main_window.change_theme)
        top.addWidget(QLabel("🎨"))
        top.addWidget(main_window.theme_combo)

        # --- ComboBox sizing (language & theme) ---
        main_window.lang_combo.setFixedWidth(110)
        main_window.theme_combo.setFixedWidth(100)
        # Minimum height already set above

        # Normalize ComboBox sizing policy (prevent upward popup)
        main_window.lang_combo.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)
        main_window.theme_combo.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)

        main_window.install_btn = QPushButton(t["btn_fix_dep"])
        main_window.install_btn.setMinimumWidth(140)
        main_window.install_btn.clicked.connect(main_window.run_install)
        top.addWidget(main_window.install_btn)

        content_layout.addLayout(top)

        # url
        main_window.url_group = QGroupBox(t["frame_url"])
        v = QVBoxLayout(main_window.url_group)
        main_window.url_entry = QLineEdit()
        PasteFix(main_window.url_entry, main_window.cmd_key)
        v.addWidget(main_window.url_entry)
        content_layout.addWidget(main_window.url_group)

        # tools
        main_window.tools_group = QGroupBox(t["frame_tools"])
        tv = QVBoxLayout(main_window.tools_group)
        hl = QHBoxLayout()
        # cookie mode radios (v6multi)
        main_window.rb_guest = QRadioButton(t["mode_guest"])
        main_window.rb_chrome = QRadioButton("Chrome")
        main_window.rb_edge = QRadioButton("Edge")
        main_window.rb_firefox = QRadioButton("Firefox")
        main_window.rb_safari = QRadioButton("Safari")
        main_window.rb_file = QRadioButton(t["mode_local_file"])

        for rb in [main_window.rb_guest, main_window.rb_chrome, main_window.rb_edge, main_window.rb_firefox,
                   main_window.rb_safari, main_window.rb_file]:
            hl.addWidget(rb)

        # Enforce exclusive radios (Qt fix, Tk semantics)
        main_window.cookie_group = QButtonGroup(main_window)
        for rb in [main_window.rb_guest, main_window.rb_chrome, main_window.rb_edge, main_window.rb_firefox,
                   main_window.rb_safari, main_window.rb_file]:
            main_window.cookie_group.addButton(rb)

        # default selection (v6multi exact)
        cookie_map = {
            "none": main_window.rb_guest,
            "chrome": main_window.rb_chrome,
            "edge": main_window.rb_edge,
            "firefox": main_window.rb_firefox,
            "safari": main_window.rb_safari,
            "file": main_window.rb_file,
        }
        # hide browsers not supported on this OS (v6multi)
        supported = main_window._os_supported_browsers()
        if "chrome" not in supported:
            main_window.rb_chrome.hide()
        if "edge" not in supported:
            main_window.rb_edge.hide()
        if "firefox" not in supported:
            main_window.rb_firefox.hide()
        if "safari" not in supported:
            main_window.rb_safari.hide()

        # sanitize cookie_source if unsupported
        if main_window.cookie_source not in supported and main_window.cookie_source not in {"file", "none"}:
            main_window.cookie_source = "none"

        cookie_map.get(main_window.cookie_source, main_window.rb_guest).setChecked(True)

        # cookie file select
        main_window.btn_sel_cookie = QPushButton(t["btn_select"])
        main_window.btn_sel_cookie.clicked.connect(main_window.select_cookie_file)
        hl.addWidget(main_window.btn_sel_cookie)

        # local file label (below file picker, v6multi)
        main_window.file_label = QLabel(t["status_no_file"])
        main_window.file_label.setStyleSheet("color:#888")
        hl.addWidget(main_window.file_label)

        tv.addLayout(hl)

        # cookie & m3u8 helpers (v6multi features)
        helper_layout = QHBoxLayout()

        # 1) cookies.txt exporter (for RE)
        main_window.btn_cookie_plugin = QPushButton(
            t.get("btn_cookie_export", "Get cookies.txt")
        )
        main_window.btn_cookie_plugin.setMinimumWidth(150)
        main_window.btn_cookie_plugin.clicked.connect(main_window.open_cookie_plugin)
        helper_layout.addWidget(main_window.btn_cookie_plugin)

        # 2) CatCatch (m3u8 capture)
        main_window.btn_catcatch = QPushButton(
            t.get("btn_catcatch", "Get m3u8 (CatCatch)")
        )
        main_window.btn_catcatch.setMinimumWidth(150)
        main_window.btn_catcatch.clicked.connect(main_window.open_catcatch)
        helper_layout.addWidget(main_window.btn_catcatch)

        helper_layout.addStretch()
        tv.addLayout(helper_layout)

        content_layout.addWidget(main_window.tools_group)

        # Windows: slightly increase button font size for better readability
        if main_window.system == "Windows":
            for btn in main_window.findChildren(QPushButton):
                btn.setStyleSheet(
                    btn.styleSheet() + " QPushButton { font-size: 13px; }"
                )

        # controls
        ctrl = QHBoxLayout()
        ev = QVBoxLayout()
        main_window.lbl_engine = QLabel(t["label_engine"])
        ev.addWidget(main_window.lbl_engine)
        main_window.engine_combo = ThemedComboBox()
        main_window.engine_combo.setFont(main_window.font_ui)
        main_window.engine_combo.addItems([t["engine_native"], t["engine_aria2"], t["engine_re"]])
        main_window.engine_combo.currentIndexChanged.connect(main_window.toggle_engine_ui)
        main_window.engine_combo.setFont(main_window.font_ui)
        main_window.engine_combo.setMinimumHeight(28)
        ev.addWidget(main_window.engine_combo)

        # Normalize ComboBox sizing policy (prevent upward popup)
        main_window.engine_combo.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)

        th = QHBoxLayout()
        main_window.lbl_threads = QLabel(t.get("label_threads", "Threads:"))
        th.addWidget(main_window.lbl_threads)
        main_window.thread_spin = QSpinBox()
        main_window.thread_spin.setRange(1, 64)
        main_window.thread_spin.setValue(8)
        main_window.thread_spin.setEnabled(False)
        th.addWidget(main_window.thread_spin)
        ev.addLayout(th)
        ctrl.addLayout(ev)

        pv = QVBoxLayout()
        ph = QHBoxLayout()
        main_window.lbl_save_path = QLabel(t["label_save_path"])
        ph.addWidget(main_window.lbl_save_path)
        main_window.path_label = QLabel(main_window.download_dir[-30:])
        main_window.path_label.setStyleSheet("color:#007AFF")
        ph.addWidget(main_window.path_label)
        ph.insertStretch(0, 1)
        pv.addLayout(ph)
        main_window.btn_path = QPushButton(t["btn_change_path"])
        main_window.btn_path.setMinimumWidth(110)
        main_window.btn_path.clicked.connect(main_window.change_download_path)
        pv.addWidget(main_window.btn_path, alignment=Qt.AlignRight)
        ctrl.addLayout(pv)
        content_layout.addLayout(ctrl)

        # start
        main_window.download_btn = QPushButton(t["btn_start"])
        main_window.download_btn.setMinimumWidth(260)
        main_window.download_btn.setMaximumWidth(340)
        main_window.download_btn.clicked.connect(main_window.toggle_download)
        content_layout.addWidget(main_window.download_btn, alignment=Qt.AlignHCenter)

        # log
        main_window.lbl_log = QLabel(t["label_log"])
        content_layout.addWidget(main_window.lbl_log)
        main_window.log_text = QPlainTextEdit()
        main_window.log_text.setReadOnly(True)
        content_layout.addWidget(main_window.log_text)

        for src, rb in {
            "none": main_window.rb_guest,
            "chrome": main_window.rb_chrome,
            "edge": main_window.rb_edge,
            "firefox": main_window.rb_firefox,
            "safari": main_window.rb_safari,
            "file": main_window.rb_file,
        }.items():
            rb.toggled.connect(lambda checked, s=src: checked and main_window._set_cookie_source(s))

        # file picker enabled only in file mode (startup safety)
        main_window.btn_sel_cookie.setEnabled(main_window.cookie_source == "file")
