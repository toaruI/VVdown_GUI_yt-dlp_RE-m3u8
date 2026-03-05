# -*- coding: utf-8 -*-

class DownloadHandler:
    def __init__(self, main_window):
        self.mw = main_window

    def map_exception_to_user_message(self, exc: Exception) -> str:
        text = str(exc).lower()
        is_zh = self.mw.lang == "zh"

        if "re engine only supports" in text or "m3u8" in text:
            return (
                "RE 引擎需要直接的 m3u8/mpd 链接，请对网页链接使用 yt-dlp。"
                if is_zh
                else "RE engine requires a direct m3u8/mpd URL. Please use yt-dlp."
            )

        if "not found" in text or "missing" in text:
            return (
                "缺少必要的依赖，请点击『修复依赖』。"
                if is_zh
                else "Required dependency not found. Please run Fix Dependencies."
            )

        if "stopped" in text or "cancel" in text:
            return (
                "下载已停止。"
                if is_zh
                else "Download stopped."
            )

        return (
            "发生错误，请查看上方日志。"
            if is_zh
            else "An error occurred. Please check the log above."
        )

    def reset_download_ui(self):
        t = self.mw.get_current_trans()
        self.mw.download_controller = None
        self.mw.download_btn.setText(t["btn_start"])
        self.mw.install_btn.setEnabled(True)
        self.mw.btn_path.setEnabled(True)
        self.mw.btn_sel_cookie.setEnabled(self.mw.cookie_source == "file")

    def toggle_download(self):
        t = self.mw.get_current_trans()
        if self.mw.download_controller and self.mw.download_controller._proc:
            self.mw.log_thread_safe(t.get("log_download_stop", "\\n>>> Download Stopped.\\n"), "warning")
            controller = self.mw.download_controller
            self.reset_download_ui()
            try:
                controller.stop()
            except Exception:
                pass
            return

        url = self.mw.url_entry.text().strip()
        if not url:
            msg = t.get("msg_input_url", "Please enter a URL")
            self.mw.log_thread_safe(msg + "\\n", "warning")
            return

        engine_text = self.mw.engine_combo.currentText().lower()
        is_re = ("re" in engine_text)
        if is_re:
            ul = url.lower()
            if not(ul.endswith('.m3u8') or ul.endswith('.mpd') or 'm3u8' in ul):
                msg = t.get(
                    "log_re_requires_m3u8",
                    "RE engine requires a direct m3u8/mpd URL. Please use yt-dlp for webpage URLs."
                )
                self.mw.log_thread_safe(msg + "\\n", "warning")
                return

        self.mw.log_text.clear()
        self.mw.download_btn.setText(t["btn_stop"])

        engine = "native"
        if is_re:
            engine = "re"
        elif "aria2" in engine_text:
            engine = "aria2"

        opts = {
            "engine": engine,
            "download_dir": self.mw.download_dir,
            "threads": self.mw.thread_spin.value(),
            "cookie_source": self.mw.cookie_source,
            "cookie_path": self.mw.cookie_file_path,
        }

        try:
            self.mw.download_controller = self.mw.downloader.run_threaded(url, opts)
        except Exception as e:
            msg = self.map_exception_to_user_message(e)
            self.mw.log_thread_safe(msg + "\\n", "error")
            self.mw.download_btn.setText(t["btn_start"])
            self.mw.download_controller = None
            return

        self.mw.install_btn.setEnabled(False)
        self.mw.btn_path.setEnabled(False)
        self.mw.btn_sel_cookie.setEnabled(False)

    def handle_download_done(self, success):
        self.reset_download_ui()
