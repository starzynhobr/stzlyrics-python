from __future__ import annotations

import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon


class TrayController(QObject):
    open_settings_requested = Signal()
    open_cache_requested = Signal()
    reload_config_requested = Signal()
    toggle_visible_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        app = QApplication.instance()
        assert app is not None

        self.tray = QSystemTrayIcon(app.style().standardIcon(QStyle.SP_MediaPlay), app)
        self.menu = QMenu()

        self.action_settings = QAction("Configurações...", self.menu)
        self.action_settings.triggered.connect(self.open_settings_requested.emit)
        self.menu.addAction(self.action_settings)

        self.action_open_cache = QAction("Abrir pasta do cache", self.menu)
        self.action_open_cache.triggered.connect(self.open_cache_requested.emit)
        self.menu.addAction(self.action_open_cache)

        self.action_reload_config = QAction("Recarregar config", self.menu)
        self.action_reload_config.triggered.connect(self.reload_config_requested.emit)
        self.menu.addAction(self.action_reload_config)

        self.menu.addSeparator()

        self.action_quit = QAction("Sair", self.menu)
        self.action_quit.triggered.connect(self.quit_requested.emit)
        self.menu.addAction(self.action_quit)

        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)

    def show(self) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def hide(self) -> None:
        self.tray.hide()

    def set_tooltip(self, text: str) -> None:
        self.tray.setToolTip((text or "STZLyrics Overlay")[:250])

    def open_folder(self, folder: str) -> None:
        if os.path.isdir(folder) and hasattr(os, "startfile"):
            os.startfile(folder)  # type: ignore[attr-defined]

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_visible_requested.emit()
