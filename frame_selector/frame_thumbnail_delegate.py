"""
Custom QStyledItemDelegate for rendering frame cards in a grid.
Each card shows a thumbnail preview and frame label.
"""

from PyQt5.QtWidgets import QStyledItemDelegate, QStyle
from PyQt5.QtGui import QPainter, QPixmap, QColor, QFont, QPen, QBrush
from PyQt5.QtCore import Qt, QRect, QSize, QModelIndex, QRectF

# Card layout constants
CARD_SIZE = 120
CARD_PADDING = 6
LABEL_HEIGHT = 22
THUMB_PADDING = 4
CORNER_RADIUS = 6

# Custom data role to flag remove button hit (Legacy - not used but kept for compat)
REMOVE_ROLE = Qt.UserRole + 1


class FrameCardDelegate(QStyledItemDelegate):
    """
    Renders each frame as a grid card:

    ┌─────────────────┐
    │                 │
    │   thumbnail     │
    │    preview      │
    │                 │
    ├─────────────────┤
    │    F 0          │
    └─────────────────┘

    - Single click on card = clone to current timeline position
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Colors matching Krita's dark theme
        self._card_bg = QColor(45, 45, 50)
        self._card_hover = QColor(55, 55, 62)
        self._card_selected = QColor(50, 85, 140)
        self._card_border = QColor(70, 70, 75)
        self._card_border_hover = QColor(100, 140, 200)
        self._thumb_bg = QColor(255, 255, 255)
        self._text_color = QColor(210, 210, 215)
        self._text_muted = QColor(140, 140, 145)

    def sizeHint(self, option, index: QModelIndex) -> QSize:
        return QSize(CARD_SIZE, CARD_SIZE)

    def paint(self, painter: QPainter, option, index: QModelIndex):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = option.rect.adjusted(
            CARD_PADDING, CARD_PADDING,
            -CARD_PADDING, -CARD_PADDING
        )
        card_rect = QRectF(rect)

        is_hovered = bool(option.state & QStyle.State_MouseOver)
        is_selected = bool(option.state & QStyle.State_Selected)

        # ── Card background ──
        if is_selected:
            bg = self._card_selected
            border = self._card_border_hover
        elif is_hovered:
            bg = self._card_hover
            border = self._card_border_hover
        else:
            bg = self._card_bg
            border = self._card_border

        painter.setBrush(QBrush(bg))
        painter.setPen(QPen(border, 1.5))
        painter.drawRoundedRect(card_rect, CORNER_RADIUS, CORNER_RADIUS)

        # ── Thumbnail area ──
        thumb_rect = QRect(
            rect.x() + THUMB_PADDING,
            rect.y() + THUMB_PADDING,
            rect.width() - (THUMB_PADDING * 2),
            rect.height() - LABEL_HEIGHT - (THUMB_PADDING * 2)
        )

        # Thumbnail background
        painter.setBrush(QBrush(self._thumb_bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(thumb_rect), 3, 3)

        # Draw the thumbnail image
        thumbnail = index.data(Qt.DecorationRole)

        if isinstance(thumbnail, QPixmap) and not thumbnail.isNull():
            scaled = thumbnail.scaled(
                thumb_rect.width(),
                thumb_rect.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            px = thumb_rect.x() + (thumb_rect.width() - scaled.width()) // 2
            py = thumb_rect.y() + (thumb_rect.height() - scaled.height()) // 2
            painter.drawPixmap(px, py, scaled)
        else:
            # Placeholder
            painter.setPen(self._text_muted)
            font = QFont()
            font.setPixelSize(24)
            painter.setFont(font)
            painter.drawText(thumb_rect, Qt.AlignCenter, "?")

        # ── Label area ──
        label_rect = QRect(
            rect.x() + THUMB_PADDING,
            rect.bottom() - LABEL_HEIGHT - 2,
            rect.width() - (THUMB_PADDING * 2),
            LABEL_HEIGHT
        )

        label = index.data(Qt.DisplayRole) or ""
        painter.setPen(self._text_color)
        font = QFont()
        font.setPixelSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(label_rect, Qt.AlignCenter | Qt.AlignVCenter, label)

        painter.restore()
