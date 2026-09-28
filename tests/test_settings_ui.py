from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.config import AppConfig
from app.i18n import SETTINGS_UI_TEXTS, tr_settings_ui
from app.ui.settings_window import SettingsWindow
from app.ui.system_tray import TrayController


def test_settings_and_tray_labels_are_translated():
    app = QApplication.instance() or QApplication([])
    window = SettingsWindow(AppConfig())
    tray = TrayController()
    for language in SETTINGS_UI_TEXTS:
        window.language_combo.setCurrentText(language)
        tray.set_language(language)
        assert window.tabs.tabText(0) == tr_settings_ui(language, "tab_appearance")
        assert window.tabs.tabText(1) == tr_settings_ui(language, "tab_mode")
        assert window.tabs.tabText(2) == tr_settings_ui(language, "tab_general")
        tooltip = tr_settings_ui(language, "offset_tooltip")
        assert window.offset_spin.toolTip() == tooltip
        assert window._label_offset_seconds.toolTip() == tooltip
        assert tray.preset_menu.title() == tr_settings_ui(language, "label_mode_preset")
        for preset, token in (("minimal", "preset_minimal"), ("detailed", "preset_detailed"),
                              ("context_2_2", "preset_context_2_2")):
            assert tray.preset_actions[preset].text() == tr_settings_ui(language, token)
            assert not tray.preset_actions[preset].text().startswith("preset_")
    window.close()
    tray.hide()


def test_validation_message_only_takes_space_when_needed():
    app = QApplication.instance() or QApplication([])
    window = SettingsWindow(AppConfig())
    assert window.validation_label.isHidden()
    window.font_color_edit.setText("invalid")
    window._emit_save()
    assert not window.validation_label.isHidden()
    window.font_color_edit.setText("#FFFFFFFF")
    assert window.validation_label.isHidden()
    window.close()


def test_settings_save_keeps_existing_payload():
    app = QApplication.instance() or QApplication([])
    window = SettingsWindow(AppConfig())
    values = []
    window.save_requested.connect(values.append)
    window.tabs.setCurrentIndex(1)
    window.layout_preset_combo.setCurrentIndex(window.layout_preset_combo.findData("context_2_2"))
    window.always_on_top_check.setChecked(False)
    window._emit_save()
    assert len(values) == 1
    assert values[0].layout_preset == "context_2_2"
    assert values[0].always_on_top is False
    assert values[0].font_color == "#FFFFFFFF"
    window.close()


def test_save_feedback_follows_confirmed_save_and_resets_on_edit():
    app = QApplication.instance() or QApplication([])
    window = SettingsWindow(AppConfig())
    initial_text = tr_settings_ui(window.language_combo.currentText(), "save")
    assert window.save_button.text() == initial_text

    window._emit_save()
    assert window.save_button.text() == initial_text
    window.mark_saved()
    assert window.save_button.text() == tr_settings_ui(window.language_combo.currentText(), "saved")

    window.offset_spin.setValue(window.offset_spin.value() + 0.05)
    assert window.save_button.text() == initial_text
    window.close()


def test_interactive_controls_use_hand_cursor():
    app = QApplication.instance() or QApplication([])
    window = SettingsWindow(AppConfig())
    for widget in (
        window.tabs.tabBar(), window.save_button, window.cancel_button,
        window.clear_cache_button, window.font_color_pick_button,
        window.shadow_enabled_check, window.language_combo,
        window.layout_preset_combo, window.font_size_spin, window.offset_spin,
    ):
        assert widget.cursor().shape() == Qt.PointingHandCursor
    window.close()
