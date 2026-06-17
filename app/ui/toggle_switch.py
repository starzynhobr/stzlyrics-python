from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton

ACCENT_DEFAULT = "#ff5a1f"
TRACK_OFF = "#2a2a31"
THUMB_OFF = "#7d7d85"
THUMB_ON = "#ffffff"
TEXT_COLOR = "#b9b9c0"


class ToggleSwitch(QAbstractButton):
    """Animated on/off switch with a trailing label.

    Drop-in for QCheckBox in the parts of the UI that only use
    text / isChecked / setChecked / toggled (all provided by QAbstractButton).
    """

    def __init__(self, parent=None, accent: str = ACCENT_DEFAULT) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._track_w = 38
        self._track_h = 21
        self._thumb_margin = 3
        self._text_gap = 10
        self._accent = QColor(accent)
        self._track_off = QColor(TRACK_OFF)
        self._thumb_off = QColor(THUMB_OFF)
        self._thumb_on = QColor(THUMB_ON)
        self._text_color = QColor(TEXT_COLOR)
        self._offset = 0.0  # thumb position, 0.0 (off) .. 1.0 (on)
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        target = 1.0 if checked else 0.0
        if not self.isVisible():
            # Avoid an animation flash for state set during initial load.
            self.setOffset(target)
            return
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(target)
        self._anim.start()

    def getOffset(self) -> float:
        return self._offset

    def setOffset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, getOffset, setOffset)

    def sizeHint(self) -> QSize:
        height = max(self._track_h, self.fontMetrics().height())
        width = self._track_w
        if self.text():
            width += self._text_gap + self.fontMetrics().horizontalAdvance(self.text())
        return QSize(width, height)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        track_y = (self.height() - self._track_h) / 2.0
        track_rect = QRectF(0.0, track_y, self._track_w, self._track_h)
        radius = self._track_h / 2.0
        painter.setBrush(self._lerp(self._track_off, self._accent, self._offset))
        painter.drawRoundedRect(track_rect, radius, radius)

        diameter = self._track_h - 2 * self._thumb_margin
        travel = self._track_w - 2 * self._thumb_margin - diameter
        thumb_x = self._thumb_margin + self._offset * travel
        painter.setBrush(self._lerp(self._thumb_off, self._thumb_on, self._offset))
        painter.drawEllipse(QRectF(thumb_x, track_y + self._thumb_margin, diameter, diameter))

        if self.text():
            painter.setPen(self._text_color)
            text_rect = QRectF(
                self._track_w + self._text_gap,
                0.0,
                self.width() - self._track_w - self._text_gap,
                self.height(),
            )
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self.text())

    @staticmethod
    def _lerp(start: QColor, end: QColor, t: float) -> QColor:
        return QColor(
            int(start.red() + (end.red() - start.red()) * t),
            int(start.green() + (end.green() - start.green()) * t),
            int(start.blue() + (end.blue() - start.blue()) * t),
        )
