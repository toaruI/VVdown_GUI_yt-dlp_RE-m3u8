# -*- coding: utf-8 -*-
import os
import webbrowser

from PySide6.QtWidgets import QFileDialog

from utils import resolve_cookie_plugin_url


class CookieManager:
    def __init__(self, main_window):
        self.mw = main_window

    def set_cookie_source(self, source: str):
        self.mw.cookie_source = source
        self.mw.update_config("cookie_source", source)

        self.mw.btn_sel_cookie.setEnabled(source == "file")

        if source != "file" and not self.mw.cookie_file_path:
            self.mw.file_label.setText(self.mw.get_current_trans()["status_no_file"])

        t = self.mw.get_current_trans()
        if source == "none":
            self.mw.log_thread_safe(t.get("log_warning_guest", "Warning: Guest mode"), "warning")
        elif source == "file":
            self.mw.log_thread_safe(t.get("log_mode_file", "Mode: Cookie file"), "info")
        else:
            self.mw.log_thread_safe(
                t.get("log_mode_browser", "Mode: {} Cookie").format(source.capitalize()),
                "info",
            )
        self.update_download_enabled()

    def update_download_enabled(self):
        is_windows = self.mw.system == "Windows"
        using_browser_cookie = self.mw.cookie_source in {"chrome", "edge", "firefox", "safari"}
        using_local_file = self.mw.cookie_source == "file"
        local_file_missing = using_local_file and not self.mw.cookie_file_path

        if is_windows and using_browser_cookie:
            self.mw.download_btn.setEnabled(False)
            t = self.mw.get_current_trans()
            msg = t.get(
                "log_win_browser_cookie_guide",
                "⚠️ Windows cannot extract browser cookies directly.\n"
                "Please use 'Get cookies.txt' button to install the browser extension,\n"
                "then export cookies and select 'Local File' mode."
            )
            if not getattr(self.mw, "_win_cookie_warned", False):
                self.mw._win_cookie_warned = True
                self.mw.log_thread_safe(msg + "\n", "warning")
            return

        if local_file_missing:
            self.mw.download_btn.setEnabled(False)
            t = self.mw.get_current_trans()
            msg = t.get(
                "log_local_cookie_missing",
                "Local cookie file selected but no file chosen."
            )
            if not getattr(self.mw, "_local_cookie_warned", False):
                self.mw._local_cookie_warned = True
                self.mw.log_thread_safe(msg + "\n", "warning")
            return

        self.mw.download_btn.setEnabled(True)
        self.mw._win_cookie_warned = False
        self.mw._local_cookie_warned = False

    def select_cookie_file(self):
        f, _ = QFileDialog.getOpenFileName(self.mw, "Select cookie file", os.path.expanduser("~"), "Text Files (*.txt)")
        if f:
            self.mw.cookie_file_path = f
            self.mw.file_label.setText(os.path.basename(f))
            self.mw.update_config("cookie_path", f)
        self.update_download_enabled()

    def open_cookie_plugin(self):
        url = resolve_cookie_plugin_url(
            browser=self.mw.cookie_source,
            system=self.mw.system,
            prefer="cookies_txt",
        )
        if not url:
            self.mw.log_thread_safe("No suitable cookies.txt exporter found for this browser.\n", "warning")
            return
        webbrowser.open(url)

    def open_catcatch(self):
        url = resolve_cookie_plugin_url(
            browser=self.mw.cookie_source,
            system=self.mw.system,
            prefer="catcatch",
        )
        if not url:
            self.mw.log_thread_safe("CatCatch is not available for this browser.\n", "warning")
            return
        webbrowser.open(url)
