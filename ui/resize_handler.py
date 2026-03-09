# -*- coding: utf-8 -*-
"""
Frameless window resize handler.
Detects mouse on window edges and handles drag-to-resize.
"""
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QMouseEvent


class ResizeHandler:
    """
    给无边框窗口添加边缘拖拽缩放功能。

    使用方式：
        在 MainWindow 中：
        self.resize_handler = ResizeHandler(self, border_width=6)

        然后在 mousePressEvent / mouseMoveEvent / mouseReleaseEvent 中
        委托给 resize_handler。
    """

    # 边缘区域枚举
    EDGE_NONE = 0
    EDGE_TOP = 1
    EDGE_BOTTOM = 2
    EDGE_LEFT = 4
    EDGE_RIGHT = 8
    EDGE_TOP_LEFT = EDGE_TOP | EDGE_LEFT
    EDGE_TOP_RIGHT = EDGE_TOP | EDGE_RIGHT
    EDGE_BOTTOM_LEFT = EDGE_BOTTOM | EDGE_LEFT
    EDGE_BOTTOM_RIGHT = EDGE_BOTTOM | EDGE_RIGHT

    # 边缘方向 → 光标样式
    CURSOR_MAP = {
        EDGE_TOP: Qt.SizeVerCursor,
        EDGE_BOTTOM: Qt.SizeVerCursor,
        EDGE_LEFT: Qt.SizeHorCursor,
        EDGE_RIGHT: Qt.SizeHorCursor,
        EDGE_TOP_LEFT: Qt.SizeFDiagCursor,
        EDGE_BOTTOM_RIGHT: Qt.SizeFDiagCursor,
        EDGE_TOP_RIGHT: Qt.SizeBDiagCursor,
        EDGE_BOTTOM_LEFT: Qt.SizeBDiagCursor,
    }

    def __init__(self, window, border_width: int = 6):
        self._window = window
        self._border_width = border_width
        self._resizing = False
        self._resize_edge = self.EDGE_NONE
        self._drag_start_pos = None
        self._drag_start_geo = None

    @property
    def border_width(self) -> int:
        return self._border_width

    def detect_edge(self, pos: QPoint) -> int:
        """检测鼠标在窗口的哪个边缘"""
        rect = self._window.rect()
        b = self._border_width
        edge = self.EDGE_NONE

        if pos.x() <= b:
            edge |= self.EDGE_LEFT
        elif pos.x() >= rect.width() - b:
            edge |= self.EDGE_RIGHT

        if pos.y() <= b:
            edge |= self.EDGE_TOP
        elif pos.y() >= rect.height() - b:
            edge |= self.EDGE_BOTTOM

        return edge

    def update_cursor(self, pos: QPoint) -> bool:
        """根据鼠标位置更新光标样式。返回是否在边缘区域"""
        edge = self.detect_edge(pos)
        cursor = self.CURSOR_MAP.get(edge)
        if cursor:
            self._window.setCursor(cursor)
            return True
        else:
            self._window.unsetCursor()
            return False

    def try_start_resize(self, event: QMouseEvent) -> bool:
        """
        尝试开始缩放。
        如果鼠标在边缘区域，开始缩放并返回 True；
        否则返回 False（调用方继续处理为窗口拖拽等）。
        """
        edge = self.detect_edge(event.pos())
        if edge == self.EDGE_NONE:
            return False

        self._resizing = True
        self._resize_edge = edge
        self._drag_start_pos = event.globalPosition().toPoint()
        self._drag_start_geo = self._window.geometry()
        return True

    def handle_resize(self, event: QMouseEvent) -> bool:
        """处理拖拽缩放中的鼠标移动。返回是否正在缩放"""
        if not self._resizing:
            return False

        delta = event.globalPosition().toPoint() - self._drag_start_pos
        geo = QRect(self._drag_start_geo)
        min_w = self._window.minimumWidth()
        min_h = self._window.minimumHeight()

        if self._resize_edge & self.EDGE_LEFT:
            new_left = geo.left() + delta.x()
            if geo.right() - new_left >= min_w:
                geo.setLeft(new_left)

        if self._resize_edge & self.EDGE_RIGHT:
            new_width = self._drag_start_geo.width() + delta.x()
            if new_width >= min_w:
                geo.setRight(geo.left() + new_width)

        if self._resize_edge & self.EDGE_TOP:
            new_top = geo.top() + delta.y()
            if geo.bottom() - new_top >= min_h:
                geo.setTop(new_top)

        if self._resize_edge & self.EDGE_BOTTOM:
            new_height = self._drag_start_geo.height() + delta.y()
            if new_height >= min_h:
                geo.setBottom(geo.top() + new_height)

        self._window.setGeometry(geo)
        return True

    def end_resize(self) -> bool:
        """结束缩放。返回之前是否在缩放"""
        was_resizing = self._resizing
        self._resizing = False
        self._resize_edge = self.EDGE_NONE
        self._drag_start_pos = None
        self._drag_start_geo = None
        return was_resizing

    @property
    def is_resizing(self) -> bool:
        return self._resizing
