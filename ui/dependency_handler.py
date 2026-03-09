# -*- coding: utf-8 -*-
import threading

from PySide6.QtCore import QTimer

from config.config import IS_MAC


class DependencyHandler:
    def __init__(self, main_window):
        self.mw = main_window

    def run_install(self):
        t = self.mw.get_current_trans()
        self.mw.install_btn.setEnabled(False)
        self.mw.install_btn.setText(t.get("btn_fix_dep_running", "Fixing..."))

        controller = self.mw.installer.install_all_threaded()

        def watcher():
            success = True
            try:
                th = getattr(controller, "_thread", None)
                if th is not None:
                    th.join()
                else:
                    is_alive = getattr(controller, "is_alive", None)
                    if callable(is_alive):
                        while is_alive():
                            threading.Event().wait(0.2)
            except Exception:
                success = False
            self.mw.installer_finished_signal.emit(success)

        threading.Thread(target=watcher, daemon=True).start()

    def on_installer_finished(self, success: bool):
        t = self.mw.get_current_trans()
        if success:
            self.mw.log_thread_safe(t.get("msg_fix_done", "Finished"), "success")
        else:
            self.mw.log_thread_safe(t.get("msg_fix_failed", "Dependency installation finished with errors"), "warning")
        self.mw.install_btn.setEnabled(True)
        self.mw.install_btn.setText(t["btn_fix_dep"])

    def check_deps_on_start(self):
        def task():
            try:
                status = self.mw.installer.check_status()
                t = self.mw.get_current_trans()

                if not status.get("yt-dlp"):
                    self.mw.log_thread_safe(t.get("log_check_yt_fail", "yt-dlp not found"), "warning")

                if not status.get("ffmpeg"):
                    self.mw.log_thread_safe(t.get("log_check_re_warning", "ffmpeg not found"), "warning")

                if IS_MAC and not status.get("aria2"):
                    self.mw._aria2_available = False

                    def hide_aria2():
                        if self.mw.engine_combo.count() >= 3:
                            self.mw.engine_combo.removeItem(1)

                    QTimer.singleShot(0, hide_aria2)
                else:
                    self.mw._aria2_available = True

            except Exception:
                pass

        self.mw.threadpool.start(task)
