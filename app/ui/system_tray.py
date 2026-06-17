from __future__ import annotations

import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from app.i18n import tr_ui
from app.ui.app_icon import load_tray_icon
from app.ui.theme import load_stylesheet


class TrayController(QObject):
    open_settings_requested = Signal()
    open_cache_requested = Signal()
    reload_current_lyrics_requested = Signal()
    reload_config_requested = Signal()
    toggle_visible_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        app = QApplication.instance()
        assert app is not None
        self._language_code = "PT-BR"
        tray_icon = load_tray_icon()
        if tray_icon.isNull():
            tray_icon = app.style().standardIcon(QStyle.SP_MediaPlay)
        self.tray = QSystemTrayIcon(tray_icon, app)
        self.menu = QMenu()
        self.menu.setStyleSheet(load_stylesheet())

        self.action_settings = QAction("", self.menu)
        self.action_settings.triggered.connect(self.open_settings_requested.emit)
        self.menu.addAction(self.action_settings)

        self.action_open_cache = QAction("", self.menu)
        self.action_open_cache.triggered.connect(self.open_cache_requested.emit)
        self.menu.addAction(self.action_open_cache)

        self.action_reload_current_lyrics = QAction("", self.menu)
        self.action_reload_current_lyrics.triggered.connect(self.reload_current_lyrics_requested.emit)
        self.menu.addAction(self.action_reload_current_lyrics)

        self.action_reload_config = QAction("", self.menu)
        self.action_reload_config.triggered.connect(self.reload_config_requested.emit)
        self.menu.addAction(self.action_reload_config)

        self.menu.addSeparator()

        self.action_quit = QAction("", self.menu)
        self.action_quit.triggered.connect(self.quit_requested.emit)
        self.menu.addAction(self.action_quit)

        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)
        self.set_language(self._language_code)

    def show(self) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def hide(self) -> None:
        self.tray.hide()

    def set_tooltip(self, text: str) -> None:
        self.tray.setToolTip((text or tr_ui(self._language_code, "app_name"))[:250])

    def set_language(self, language_code: str) -> None:
        self._language_code = language_code or self._language_code
        self.action_settings.setText(tr_ui(self._language_code, "tray_settings"))
        self.action_open_cache.setText(tr_ui(self._language_code, "tray_open_cache"))
        self.action_reload_current_lyrics.setText(tr_ui(self._language_code, "tray_reload_current_lyrics"))
        self.action_reload_config.setText(tr_ui(self._language_code, "tray_reload_config"))
        self.action_quit.setText(tr_ui(self._language_code, "tray_quit"))

    def open_folder(self, folder: str) -> None:
        if os.path.isdir(folder) and hasattr(os, "startfile"):
            os.startfile(folder)  # type: ignore[attr-defined]

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_visible_requested.emit()
