# -*- coding: utf-8 -*-
"""
Small PySide6 helper utilities to replace the original Tk widgets helpers.
Provides a minimal setup_styles and a PasteFix helper used by the rewritten UI.
"""
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import QObject, Qt


def setup_styles(system_name):
    """Return (font_ui, font_bold, font_log) similar to the old widgets contract."""
    if system_name == "Darwin":
        font_ui = QFont("Helvetica", 12)
        font_bold = QFont("Helvetica", 12, QFont.Bold)
        font_log = QFont("Courier", 11)
    else:
        font_ui = QFont("Arial", 11)
        font_bold = QFont("Arial", 11, QFont.Bold)
        font_log = QFont("Consolas", 11)
    return font_ui, font_bold, font_log


class PasteFix(QObject):
    """Small helper to normalize paste behavior on QLineEdit.
    Usage: PasteFix(line_edit, cmd_key)
    """
    def __init__(self, line_edit: QLineEdit, cmd_key="Control"):
        super().__init__(line_edit)
        self._le = line_edit
        # install an event filter to handle paste shortcuts if needed
        self._le.installEventFilter(self)

    def eventFilter(self, obj, event):
        # allow normal paste, but you could add normalization here if needed
        return super().eventFilter(obj, event)