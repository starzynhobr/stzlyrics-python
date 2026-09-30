from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication, QBoxLayout

from app.config import AppConfig, AppPaths, load_config, save_config
from app.controller import AppController
from app.i18n import UI_TEXTS, tr_ui
from app.ui.system_tray import TrayController
from app.ui.welcome_window import WelcomeWindow, _KEYS, welcome_text


def paths_at(root):
    return AppPaths(root, root / "config.json", root / "cache", root / "logs", root / "cache/index.json")


def test_preview_and_dismissal_do_not_apply_preferences():
    app = QApplication.instance() or QApplication([])
    config = AppConfig()
    original = config.to_dict()
    window = WelcomeWindow(config)
    requests = []
    settings = []
    window.start_requested.connect(requests.append)
    window.settings_requested.connect(lambda: settings.append(True))
    window.preset_buttons["context_2_2"].click()
    assert window.preview.preset == "context_2_2"
    assert config.to_dict() == original
    window.settings_button.click()
    assert settings == [True]
    window.later_button.click()
    assert requests == []
    assert config.to_dict() == original
    window.start_button.click()
    assert requests == ["context_2_2"]
    window.close()


def test_completion_persists_and_preserves_existing_user_preferences(tmp_path):
    config = AppConfig.from_dict({
        "font": {"size": 34, "preset_colors": {"minimal": "#12ABCD"}},
        "overlay": {"positions": {"DISPLAY2|detailed": {"x": 2000, "y": 80}}},
    })
    assert config.onboarding_completed is False
    paths = paths_at(tmp_path)
    save_config(paths, config)
    original = config.to_dict()
    controller = SimpleNamespace(config=config, paths=paths, logger=Mock(), overlay=Mock(),
                                 tray=Mock(), _settings_window=Mock(), _welcome_window=Mock())
    AppController._complete_welcome(controller, "minimal")
    stored = load_config(paths)
    assert stored.onboarding_completed is True
    assert stored.overlay.layout_preset == "minimal"
    assert stored.font.size == 34
    assert stored.font.preset_colors == original["font"]["preset_colors"]
    assert stored.overlay.positions == original["overlay"]["positions"]
    controller._welcome_window.accept.assert_called_once()
    controller.overlay.apply_config.assert_called_once_with(config)
    controller._settings_window.load_from_config.assert_called_once_with(config)


def test_failed_save_keeps_welcome_open_and_preferences_unchanged(tmp_path):
    config = AppConfig()
    original = config.to_dict()
    controller = SimpleNamespace(config=config, paths=paths_at(tmp_path), logger=Mock(),
                                 overlay=Mock(), tray=Mock(), _settings_window=None, _welcome_window=Mock())
    with patch("app.controller.save_config", side_effect=OSError("disk unavailable")):
        AppController._complete_welcome(controller, "context_2_2")
    assert config.to_dict() == original
    controller._welcome_window.accept.assert_not_called()
    controller._welcome_window.show_save_error.assert_called_once()
    controller.overlay.apply_config.assert_not_called()


def test_start_shows_welcome_until_completed():
    config = AppConfig()
    controller = SimpleNamespace(config=config, overlay=Mock(), tray=Mock(), _tr=lambda key: key,
                                 _ui_clock_timer=Mock(), media_service=Mock(), _open_welcome_window=Mock())
    AppController.start(controller)
    controller._open_welcome_window.assert_called_once()
    config.onboarding_completed = True
    controller._open_welcome_window.reset_mock()
    AppController.start(controller)
    controller._open_welcome_window.assert_not_called()
    controller.media_service.start.assert_called()


def test_welcome_translations_and_tray_action():
    app = QApplication.instance() or QApplication([])
    tray = TrayController()
    requests = []
    tray.open_welcome_requested.connect(lambda: requests.append(True))
    for language in UI_TEXTS:
        window = WelcomeWindow(AppConfig.from_dict({"lyrics": {"language": language}}))
        assert window.start_button.text() == welcome_text(language, "begin")
        for key in _KEYS:
            assert welcome_text(language, key) and welcome_text(language, key) != key
        tray.set_language(language)
        assert tray.action_welcome.text() == tr_ui(language, "tray_welcome")
        window.close()
    tray.action_welcome.trigger()
    assert requests == [True]
    tray.hide()


def test_preview_timer_stops_when_closed_and_narrow_layout_stacks():
    app = QApplication.instance() or QApplication([])
    window = WelcomeWindow(AppConfig())
    window.resize(660, 520)
    window.show()
    app.processEvents()
    assert window.hero.direction() == QBoxLayout.TopToBottom
    assert window.preview.timer.isActive()
    window.close()
    app.processEvents()
    assert not window.preview.timer.isActive()
