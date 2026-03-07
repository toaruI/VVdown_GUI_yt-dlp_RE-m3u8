# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QPalette
from PySide6.QtCore import Qt
import qdarktheme
from .widgets import apply_global_style

class ThemeManager:
    def __init__(self, main_window):
        self.mw = main_window

    def apply_full_theme(self, first_time=False):
        app = QApplication.instance()

        qdarktheme.setup_theme(self.mw.theme)

        if first_time:
            apply_global_style(app)

        pal = qdarktheme.load_palette(self.mw.theme)
        bg = pal.color(QPalette.Window).name()

        if hasattr(self.mw, "_content"):
            self.mw._content.setStyleSheet(f"""
                QWidget#MainWindowRoot {{
                    background-color: {bg};
                    border: 1px solid {bg};
                    border-radius: 14px;
                    outline: none;
                }}
            """)

        # FORCE transparency on the outer container.
        # We REMOVE setAutoFillBackground and the solid QMainWindow stylesheet
        # to allow WA_TranslucentBackground to work correctly.
        try:
            self.mw.setAttribute(Qt.WA_StyledBackground, True)

            # Do NOT setAutoFillBackground(True) on the top-level window
            self.mw.setAutoFillBackground(False)

            # also ensure central widget (if any) follows the palette and is styled
            cw = None
            try:
                cw = self.mw.centralWidget()
            except Exception:
                cw = None

            if cw is None:
                cw = getattr(self.mw, "_content", None)

            if cw is not None:
                cw.setAttribute(Qt.WA_StyledBackground, True)
                cw.setAutoFillBackground(False)

            # Explicitly force the top-level container to be transparent via CSS
            # Using QWidget#MainWindow targets our main window without affecting children.
            self.mw.setStyleSheet("QWidget#MainWindow { background: transparent; border: none; }")
        except Exception:
            pass
        
        if hasattr(self.mw, "title_bar"):
            self.mw.title_bar.update_title_color()
        
        self.deep_refresh(self.mw)

    @staticmethod
    def deep_refresh(widget):
        for child in widget.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def change_theme(self):
        current_idx = self.mw.theme_combo.currentIndex()
        if current_idx == 0:
            new_theme = "auto"
        elif current_idx == 1:
            new_theme = "dark"
        else:
            new_theme = "light"

        if new_theme == self.mw.theme:
            return

        self.mw.theme = new_theme
        self.apply_full_theme()
        self.mw.update_config("theme", self.mw.theme)
        
        # We need UI manager to refresh text, but can assume mw handles routing
        if hasattr(self.mw, "ui_state_manager"):
            self.mw.ui_state_manager.refresh_text()
        else:
            if hasattr(self.mw, "_refresh_text"):
                self.mw._refresh_text()

        t = self.mw.get_current_trans()
        msg = t.get("log_theme_switched", "Theme switched to {}.")
        self.mw.log_thread_safe(msg.format(self.mw.theme), "info")
