# -*- coding: utf-8 -*-
"""
PySide6 UI helpers — premium widgets and global styles.
"""
from PySide6.QtCore import QObject, Qt, QEvent
from PySide6.QtGui import QFont, QKeySequence
from PySide6.QtWidgets import QLineEdit, QComboBox, QApplication

from config.config import IS_MAC, IS_WIN


def setup_styles(system_name):
    """Return (font_ui, font_bold, font_log) with premium UI choices."""
    if system_name == "Darwin":
        font_ui = QFont(".AppleSystemUIFont", 13)
        if not font_ui.exactMatch():
            font_ui = QFont("Helvetica Neue", 13)
        font_bold = QFont(font_ui)
        font_bold.setBold(True)
        font_log = QFont("Menlo", 12)
    elif system_name == "Windows":
        font_ui = QFont("Microsoft YaHei UI", 9)
        font_ui.setHintingPreference(QFont.PreferFullHinting)
        font_bold = QFont("Microsoft YaHei UI", 9, QFont.Bold)
        font_bold.setHintingPreference(QFont.PreferFullHinting)
        font_log = QFont("Consolas", 10)
        font_log.setHintingPreference(QFont.PreferFullHinting)
    else:  # Linux
        font_ui = QFont("Noto Sans CJK SC", 10)
        if not font_ui.exactMatch():
            font_ui = QFont("Segoe UI", 10)
        font_bold = QFont(font_ui)
        font_bold.setBold(True)
        font_log = QFont("Noto Sans Mono", 11)
        if not font_log.exactMatch():
            font_log = QFont("Consolas", 11)
    return font_ui, font_bold, font_log


class ThemedComboBox(QComboBox):
    """
    A modern QComboBox that follows the qdarktheme palette.
    
    Key design decisions:
    - NO custom window flags on the popup view (these break positioning).
    - CSS-only styling for the dropdown list.
    - drop-down sub-control is transparent (no black bar).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.setMinimumHeight(30)
        from PySide6.QtWidgets import QListView
        # Force QListView to bypass macOS native popup menu overlapping behavior
        self.setView(QListView())
        # Do NOT touch self.view().window() flags — it breaks popup positioning.

    def showPopup(self):
        super().showPopup()
        popup = self.view().window()

        if popup:
            pos = self.mapToGlobal(self.rect().bottomLeft())
            pos.setY(pos.y() + 2)

            screen = self.screen()
            if screen:
                screen_geo = screen.availableGeometry()
                popup_height = popup.sizeHint().height()
                if pos.y() + popup_height > screen_geo.bottom():
                     above_y = self.mapToGlobal(self.rect().topLeft()).y() - popup_height - 2
                     pos.setY(max(above_y, screen_geo.top()))

            popup.move(pos)
            popup.setFixedWidth(self.width())


class PasteFix(QObject):
    """Small helper to normalize paste behavior on QLineEdit."""

    def __init__(self, line_edit: QLineEdit, cmd_key="Control"):
        super().__init__(line_edit)
        self._le = line_edit
        self._cmd_key = cmd_key
        self._le.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self._le and event.type() == QEvent.KeyPress:
            if event.matches(QKeySequence.Paste):
                self._handle_paste()
                return True
        return super().eventFilter(obj, event)

    def _handle_paste(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            cleaned = text.strip()
            if self._le.hasSelectedText():
                self._le.insert(cleaned)
            else:
                self._le.insert(cleaned)


# ---------------------------------------------------------------------------
# Global stylesheet — applied on top of qdarktheme
# ---------------------------------------------------------------------------

GLOBAL_STYLE = """
/* ── QPushButton ─────────────────────────────────────────── */
QPushButton {
    border-radius: 8px;
    padding: 6px 18px;
    min-height: 28px;
    background-color: palette(button);
    color: palette(button-text);
    border: 1px solid palette(mid);
    font-weight: 500;
}

QPushButton:hover {
    background-color: palette(light);
    border: 1px solid palette(highlight);
}

QPushButton:pressed {
    background-color: palette(midlight);
}

QPushButton:disabled {
    background-color: palette(window);
    color: palette(mid);
    border: 1px solid palette(mid);
}

/* ── QRadioButton — pill-style selected state ────────────── */
QRadioButton {
    spacing: 6px;
    padding: 4px 8px;
    border-radius: 12px;
    border: 1px solid transparent;
}

QRadioButton:hover {
    background-color: palette(midlight);
    border-radius: 12px;
}

QRadioButton:checked {
    background-color: palette(highlight);
    color: palette(highlighted-text);
    border-radius: 12px;
    border: 1px solid palette(highlight);
}

QRadioButton::indicator {
    width: 0px;
    height: 0px;
}

/* ── QGroupBox ───────────────────────────────────────────── */
QGroupBox {
    border: 1px solid palette(mid);
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 12px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: palette(text);
}

/* ── QPlainTextEdit (log area) ───────────────────────────── */
QPlainTextEdit {
    background-color: palette(base);
    color: palette(text);
    border: 1px solid palette(mid);
    border-radius: 8px;
    padding: 6px;
    selection-background-color: palette(highlight);
}

/* ── QLineEdit ───────────────────────────────────────────── */
QLineEdit {
    background-color: palette(base);
    color: palette(text);
    border: 1px solid palette(mid);
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 24px;
}

QLineEdit:focus {
    border: 1px solid palette(highlight);
}

/* ── QSpinBox ────────────────────────────────────────────── */
QSpinBox {
    background-color: palette(base);
    color: palette(text);
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 24px;
}

QSpinBox:focus {
    border: 1px solid palette(highlight);
}

/* ── Scrollbar — slim modern ─────────────────────────────── */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: palette(mid);
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: palette(highlight);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 8px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: palette(mid);
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""
# ---------------------------------------------------------------------------
# Platform-specific style overrides
# ---------------------------------------------------------------------------

_MACOS_STYLE = """
/* ── macOS polish ────────────────────────────────────────── */
* {
    font-family: ".AppleSystemUIFont", "Helvetica Neue", "PingFang SC", sans-serif;
}

QPlainTextEdit, QTextEdit {
    font-family: "Menlo", "SF Mono", monospace;
}

QPushButton {
    padding: 5px 16px;
    border-radius: 6px;
}

QRadioButton {
    padding: 3px 8px;
}

/* macOS 原生风格：更小的圆角 */
QGroupBox {
    border-radius: 8px;
}

QLineEdit, QSpinBox {
    border-radius: 6px;
}
"""

_WINDOWS_STYLE = """
/* ── Windows polish ──────────────────────────────────────── */
* {
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
}

QPlainTextEdit, QTextEdit {
    font-family: "Consolas", "Microsoft YaHei UI", monospace;
}

QPushButton {
    padding: 5px 16px;
}

QPushButton#WinControlButton {
    font-size: 20px;
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
}

QRadioButton {
    padding: 4px 10px;
}

QGroupBox {
    font-weight: 600;
}

QSpinBox::up-button, QSpinBox::down-button {
    width: 20px;
}
"""

_LINUX_STYLE = """
/* ── Linux polish ────────────────────────────────────────── */
* {
    font-family: "Noto Sans CJK SC", "Noto Sans", "Ubuntu", "Segoe UI", sans-serif;
}

QPlainTextEdit, QTextEdit {
    font-family: "Noto Sans Mono", "Ubuntu Mono", "Consolas", monospace;
}

QPushButton {
    padding: 5px 16px;
}

QRadioButton {
    padding: 4px 10px;
}

QGroupBox {
    font-weight: 600;
}

/* Linux GTK 主题下 SpinBox 可能偏窄 */
QSpinBox {
    padding: 4px 6px;
}

QSpinBox::up-button, QSpinBox::down-button {
    width: 20px;
}
"""


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def apply_global_style(app):
    """Apply the premium global stylesheet on QApplication (once).
    Must be called AFTER qdarktheme.setup_theme() so it appends.
    """
    current = app.styleSheet() or ""
    # Avoid accumulation: only add if not already present
    if "/* VVdown Premium */" in current:
        return
    
    extra = GLOBAL_STYLE

    if IS_MAC:
        extra += _MACOS_STYLE
    elif IS_WIN:
        extra += _WINDOWS_STYLE
    else:
        extra += _LINUX_STYLE


    app.setStyleSheet(current + "\n/* VVdown Premium */\n" + extra)
