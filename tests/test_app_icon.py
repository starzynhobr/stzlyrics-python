from PySide6.QtWidgets import QApplication

from app.config import AppConfig
from app.ui.app_icon import app_icon_path, load_app_icon, load_tray_icon, tray_icon_path
from app.ui.settings_window import SettingsWindow


def test_brand_icon_is_used_by_app_tray_and_settings_window():
    app = QApplication.instance() or QApplication([])
    assert app_icon_path() == tray_icon_path()
    assert app_icon_path().name == "logo.ico"
    assert not load_app_icon().isNull()
    assert not load_tray_icon().pixmap(16, 16).isNull()
    window = SettingsWindow(AppConfig())
    assert not window.windowIcon().isNull()
    window.close()
