from unittest.mock import patch

from PySide6.QtCore import QRect

from app.config import AppConfig
from app.ui.overlay_window import OverlayWindow


class FakeScreen:
    def __init__(self, name: str, left: int):
        self._name = name
        self._geometry = QRect(left, 0, 1920, 1080)

    def name(self):
        return self._name

    def geometry(self):
        return self._geometry

    def availableGeometry(self):
        return self._geometry


class FakeOverlay:
    _screen_scale_percent = OverlayWindow._screen_scale_percent

    def __init__(self, config):
        self._config = config
        self.position = None

    def move(self, x, y):
        self.position = (x, y)

    def width(self):
        return 960

    def height(self):
        return 84

    def _clamp_to_visible(self, screen=None):
        pass


def test_restore_prefers_saved_second_monitor_and_falls_back_temporarily():
    config = AppConfig()
    config.overlay.layout_preset = "context_2_2"
    config.set_saved_position("DISPLAY2", 100, 1920, 1080, 2100, 120,
                              layout_preset="context_2_2")
    primary = FakeScreen("DISPLAY1", 0)
    secondary = FakeScreen("DISPLAY2", 1920)
    overlay = FakeOverlay(config)

    with patch("app.ui.overlay_window.QGuiApplication.screens", return_value=[primary, secondary]), \
         patch("app.ui.overlay_window.QGuiApplication.primaryScreen", return_value=primary):
        OverlayWindow.restore_position(overlay)
        assert overlay.position == (2100, 120)

    with patch("app.ui.overlay_window.QGuiApplication.screens", return_value=[primary]), \
         patch("app.ui.overlay_window.QGuiApplication.primaryScreen", return_value=primary):
        OverlayWindow.restore_position(overlay)
        assert 0 <= overlay.position[0] < 1920
        assert config.preferred_screen_for_preset("context_2_2") == "DISPLAY2"


def test_existing_positions_determine_preferred_monitor():
    config = AppConfig()
    config.overlay.positions["DISPLAY2|100|1920x1080|context_2_2"] = {"x": 2000, "y": 10}
    assert config.preferred_screen_for_preset("context_2_2") == "DISPLAY2"
