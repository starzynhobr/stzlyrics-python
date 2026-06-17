from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from app.ui.app_icon import load_app_icon


class TitleBar(QWidget):
    """Custom draggable title bar for the frameless settings window."""

    minimize_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(40)
        self._drag_offset = None

        self.icon_label = QLabel()
        self.icon_label.setObjectName("titleIcon")
        icon = load_app_icon()
        if not icon.isNull():
            self.icon_label.setPixmap(icon.pixmap(18, 18))

        self.title_label = QLabel("")
        self.title_label.setObjectName("titleText")

        self.min_button = QPushButton("−")  # minus sign
        self.min_button.setObjectName("titleMin")
        self.close_button = QPushButton("×")  # multiplication sign
        self.close_button.setObjectName("titleClose")
        for button in (self.min_button, self.close_button):
            button.setFixedSize(34, 28)
            button.setCursor(Qt.PointingHandCursor)
            button.setFocusPolicy(Qt.NoFocus)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 6, 0)
        layout.setSpacing(8)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addStretch(1)
        layout.addWidget(self.min_button)
        layout.addWidget(self.close_button)

        self.min_button.clicked.connect(self.minimize_clicked)
        self.close_button.clicked.connect(self.close_clicked)

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and (event.buttons() & Qt.LeftButton):
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_offset = None
        event.accept()
