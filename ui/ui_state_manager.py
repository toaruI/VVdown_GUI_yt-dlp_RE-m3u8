# -*- coding: utf-8 -*-
import os
from PySide6.QtCore import QTimer
from config.config import IS_MAC

class UIStateManager:
    def __init__(self, main_window):
        self.mw = main_window

    def change_language(self):
        new_lang = "zh" if self.mw.lang_combo.currentText() == "中文" else "en"
        if new_lang == self.mw.lang:
            return
        self.mw.lang = new_lang
        self.mw.update_config("lang", self.mw.lang)

        try:
            self.mw.downloader.set_language(self.mw.lang)
            self.mw.installer.set_language(self.mw.lang)
        except Exception:
            pass

        self.refresh_text()

    def refresh_text(self):
        t = self.mw.get_current_trans()
        display_name = "macOS" if self.mw.system == "Darwin" else self.mw.system

        self.mw.setWindowTitle(f"{t['title']} ({display_name})")
        if hasattr(self.mw, 'title_bar'):
            self.mw.title_bar.update_title(self.mw.windowTitle())

        self.mw.btn_open.setText(t["btn_open_dir"])
        self.mw.btn_clear.setText(t["btn_clear_log"])
        self.mw.install_btn.setText(t["btn_fix_dep"])

        self.mw.lang_combo.blockSignals(True)
        self.mw.lang_combo.setCurrentIndex(0 if self.mw.lang == "en" else 1)
        self.mw.lang_combo.blockSignals(False)

        self.mw.url_group.setTitle(t["frame_url"])
        self.mw.tools_group.setTitle(t["frame_tools"])

        self.mw.rb_guest.setText(t["mode_guest"])
        self.mw.rb_file.setText(t["mode_local_file"])
        self.mw.btn_sel_cookie.setText(t["btn_select"])
        if not self.mw.cookie_file_path:
            self.mw.file_label.setText(t["status_no_file"])

        if hasattr(self.mw, "btn_cookie_plugin"):
            self.mw.btn_cookie_plugin.setText(
                t.get("btn_cookie_export", "Get cookies.txt")
            )
        if hasattr(self.mw, "btn_catcatch"):
            self.mw.btn_catcatch.setText(
                t.get("btn_catcatch", "Get m3u8 (CatCatch)")
            )

        self.mw.lbl_engine.setText(t["label_engine"])
        self.mw.lbl_threads.setText(t.get("label_threads", "Threads:"))

        self.mw.engine_combo.blockSignals(True)
        current_index = self.mw.engine_combo.currentIndex()

        aria2_available = True
        try:
            status = self.mw.installer.check_status()
            aria2_available = bool(status.get("aria2"))
        except Exception:
            aria2_available = getattr(self.mw, "_aria2_available", True)

        self.mw._aria2_available = aria2_available

        self.mw.engine_combo.clear()
        engines = [t["engine_native"]]
        if aria2_available:
            engines.append(t["engine_aria2"])
        engines.append(t["engine_re"])
        self.mw.engine_combo.addItems(engines)

        if current_index < self.mw.engine_combo.count():
            self.mw.engine_combo.setCurrentIndex(current_index)
        self.mw.engine_combo.blockSignals(False)

        self.mw.lbl_save_path.setText(t["label_save_path"])
        self.mw.btn_path.setText(t["btn_change_path"])
        self.mw.path_label.setText(self.mw.download_dir[-30:])

        self.mw.lbl_log.setText(t["label_log"])

        old_lang = getattr(self.mw, "_last_lang_logged", None)

        if old_lang is not None and old_lang != self.mw.lang:
            try:
                msg = t.get("log_language_switched")
                if not msg:
                    msg = ">>> Language switched to {}\n"
                self.mw.log_thread_safe(msg.format(self.mw.lang), "info")
            except Exception:
                pass

        self.mw._last_lang_logged = self.mw.lang

        self.toggle_engine_ui()

        if self.mw.download_controller and self.mw.download_controller._proc:
            self.mw.download_btn.setText(t["btn_stop"])
        else:
            self.mw.download_btn.setText(t["btn_start"])

        if hasattr(self.mw, "cookie_manager"):
            self.mw.cookie_manager.update_download_enabled()

    def restore_config_state(self):
        t = self.mw.get_current_trans()
        if self.mw.cookie_file_path and os.path.exists(self.mw.cookie_file_path):
            self.mw.file_label.setText(os.path.basename(self.mw.cookie_file_path))
            self.mw.file_label.setStyleSheet("color:#007AFF")
            try:
                self.mw.log_thread_safe(t.get("log_load_cookie_ok", "Loaded previous cookie file."), "success")
            except Exception:
                pass

    def toggle_engine_ui(self):
        is_re = self.mw.engine_combo.currentIndex() == (self.mw.engine_combo.count() - 1)

        self.mw.thread_spin.setEnabled(True)

        for rb in [self.mw.rb_chrome, self.mw.rb_edge, self.mw.rb_firefox, self.mw.rb_safari]:
            if rb.isVisible():
                rb.setEnabled(not is_re)

        if is_re and self.mw.cookie_source in {"chrome", "edge", "firefox", "safari"}:
            self.mw.rb_guest.setChecked(True)

    def apply_mac_hover_fix(self):
        self.mw.activateWindow()
        self.mw.raise_()

        def wake_up_hover():
            current_size = self.mw.size()
            self.mw.resize(current_size.width(), current_size.height() + 1)
            QTimer.singleShot(50, lambda: self.mw.resize(current_size))

        QTimer.singleShot(100, wake_up_hover)

    def toggle_maximize(self):
        normal_margins = (12, 8, 12, 24)

        if self.mw.isMaximized() or self.mw.isFullScreen():
            self.mw.showNormal()
            self.mw.layout().setContentsMargins(*normal_margins)

            if hasattr(self.mw, 'title_bar'):
                self.mw.title_bar.update_maximize_icon(False)
        else:
            self.mw.layout().setContentsMargins(0, 0, 0, 0)
            if getattr(self.mw, "system", "") == "Darwin":
                self.mw.showFullScreen()
            else:
                self.mw.showMaximized()

            if hasattr(self.mw, 'title_bar'):
                self.mw.title_bar.update_maximize_icon(True)