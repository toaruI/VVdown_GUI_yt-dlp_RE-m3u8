# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtGui import QMouseEvent
from config.config import IS_MAC

# --- Custom Frameless Title Bar (platform-aware) ---
class TitleBar(QWidget):
    """
    Native-feeling, platform-aware custom title bar.
    macOS: 13×13 traffic-light buttons with hover-reveal symbols.
    Windows: text-based window controls on the right.
    """

    HEIGHT = 38
    # macOS traffic light spec: 13px diameter, 6.5px radius, 8px gap
    MAC_BTN_SIZE = 13
    MAC_BTN_RADIUS = 6  # int for stylesheet (6.5 rounds to 6 in CSS)
    MAC_BTN_SPACING = 8

    def __init__(self, parent):
        super().__init__(parent)
        self._parent = parent
        self._drag_pos = None
        self.is_mac = IS_MAC

        self.setFixedHeight(self.HEIGHT)
        self.setObjectName("TitleBar")
        self.setMouseTracking(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

        # -------- macOS traffic lights (left) --------
        if self.is_mac:
            self._traffic = QWidget(self)
            self._traffic.setObjectName("MacTraffic")
            self._traffic.setFixedHeight(self.HEIGHT)
            self._traffic.setMouseTracking(True)

            traffic_layout = QHBoxLayout(self._traffic)
            traffic_layout.setContentsMargins(6, 0, 8, 0)
            traffic_layout.setSpacing(self.MAC_BTN_SPACING)

            self.btn_close = self._make_mac_btn("#ff5f57", "#e0443e", "×")
            self.btn_min = self._make_mac_btn("#ffbd2e", "#dea123", "−")
            self.btn_max = self._make_mac_btn("#28c840", "#1eab36", "↗")

            self.btn_close.clicked.connect(self._parent.close)
            self.btn_min.clicked.connect(self._parent.showMinimized)
            self.btn_max.clicked.connect(self._parent.showFullScreen)

            traffic_layout.addWidget(self.btn_close)
            traffic_layout.addWidget(self.btn_min)
            traffic_layout.addWidget(self.btn_max)
            layout.addWidget(self._traffic)
            layout.addSpacing(8)

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
                b.setFixedSize(36, 26)
                b.setFocusPolicy(Qt.NoFocus)
                b.setObjectName("WinControlButton")

            self.btn_min.clicked.connect(self._parent.showMinimized)
            self.btn_max.clicked.connect(self._parent.toggle_maximize)
            self.btn_close.clicked.connect(self._parent.close)

            layout.addWidget(self.btn_min)
            layout.addWidget(self.btn_max)
            layout.addWidget(self.btn_close)

        self._apply_style()
        self.update_title_color()

    # -------- helpers --------

    def _make_mac_btn(self, color: str, hover_color: str, symbol: str) -> QPushButton:
        """Create a single macOS traffic-light button with hover-reveal symbol."""
        btn = QPushButton(self)
        btn.setFixedSize(self.MAC_BTN_SIZE, self.MAC_BTN_SIZE)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setCursor(Qt.ArrowCursor)
        btn.setObjectName("MacTrafficButton")
        r = self.MAC_BTN_RADIUS
        btn.setStyleSheet(f"""
            QPushButton#MacTrafficButton {{
                background-color: {color};
                border-radius: {r}px;
                border: none;
                color: transparent;
                font-size: 9px;
                font-weight: 900;
                padding: 0px;
                text-align: center;
            }}
            QPushButton#MacTrafficButton:hover {{
                background-color: {hover_color};
                color: rgba(80, 20, 20, 0.7);
            }}
            QPushButton#MacTrafficButton:pressed {{
                background-color: {hover_color};
                color: rgba(80, 20, 20, 0.9);
            }}
        """)
        btn.setText(symbol)
        return btn

    def _apply_style(self):
        """Title bar background and label styling."""
        self.setStyleSheet("""
            QWidget#TitleBar {
                background-color: transparent;
                border: none;
            }

            QLabel#TitleLabel {
                font-weight: 600;
                font-size: 13px;
                border: none;
                background: transparent;
            }

            /* Windows controls */
            QPushButton#WinControlButton {
                background: transparent;
                color: palette(text);
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton#WinControlButton:hover {
                background-color: palette(midlight);
            }
        """)

    # -------- public API --------

    def update_title(self, text: str):
        self.title_label.setText(text)

    def update_title_color(self):
        theme = getattr(self._parent, "theme", "dark")
        if theme == "dark":
            self.title_label.setStyleSheet(
                "QLabel#TitleLabel { color: rgba(255,255,255,0.85); font-weight: 600; font-size: 13px; background: transparent; border: none; }"
            )
        else:
            self.title_label.setStyleSheet(
                "QLabel#TitleLabel { color: rgba(0,0,0,0.75); font-weight: 600; font-size: 13px; background: transparent; border: none; }"
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
