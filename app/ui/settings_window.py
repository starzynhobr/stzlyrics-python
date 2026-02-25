from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QColorDialog,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.i18n import normalize_ui_language, tr_settings_ui
from app.layout_presets import LayoutPreset, normalize_layout_preset
from app.ui.color_utils import normalize_rgba_hex, parse_rgba_hex, qcolor_from_rgba_hex, rgba_hex_from_qcolor


SUPPORTED_LANGUAGES = ["EN", "PT-BR", "ES", "IT", "DE", "FR", "JP"]


class _NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class _NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class _NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


@dataclass(slots=True)
class SettingsValues:
    font_family: str
    font_size: int
    font_color: str
    shadow_enabled: bool
    shadow_color: str
    offset_seconds: float
    language: str
    layout_preset: str
    always_on_top: bool
    click_through: bool
    snap_to_taskbar: bool


class SettingsWindow(QDialog):
    save_requested = Signal(object)  # SettingsValues

    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.setModal(False)
        self.setMinimumWidth(420)
        self._preset_font_color_drafts: dict[str, str] = {}
        self._loaded_preset_font_colors: dict[str, str] = {}
        self._loaded_default_font_color = "#FFFFFFFF"
        self._active_preset_for_font_color = LayoutPreset.DETAILED.value
        self._preset_always_on_top_drafts: dict[str, bool] = {}
        self._loaded_preset_always_on_top: dict[str, bool] = {}
        self._loaded_default_always_on_top = True
        self._preset_switch_internal = False

        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: #ff8080;")
        self.validation_label.setWordWrap(True)

        self.font_family_edit = QLineEdit()
        self.font_size_spin = _NoWheelSpinBox()
        self.font_size_spin.setRange(8, 96)

        self.font_color_edit = QLineEdit()
        self.font_color_pick_button = QPushButton()
        self.shadow_enabled_check = QCheckBox()
        self.shadow_color_edit = QLineEdit()
        self.shadow_color_pick_button = QPushButton()
        self.offset_spin = _NoWheelDoubleSpinBox()
        self.offset_spin.setRange(-30.0, 30.0)
        self.offset_spin.setDecimals(2)
        self.offset_spin.setSingleStep(0.05)

        self.language_combo = _NoWheelComboBox()
        self.language_combo.addItems(SUPPORTED_LANGUAGES)
        self.layout_preset_combo = _NoWheelComboBox()

        self.always_on_top_check = QCheckBox()
        self.click_through_check = QCheckBox()
        self.snap_check = QCheckBox()

        self._label_font = QLabel("")
        self._label_size = QLabel("")
        self._label_color_rgba = QLabel("")
        self._label_shadow_color_rgba = QLabel("")
        self._label_offset_seconds = QLabel("")
        self._label_language = QLabel("")
        self._label_mode_preset = QLabel("")
        self._blank_label_1 = QLabel("")
        self._blank_label_2 = QLabel("")
        self._blank_label_3 = QLabel("")
        self._blank_label_4 = QLabel("")

        font_color_row = self._build_color_row(self.font_color_edit, self.font_color_pick_button)
        shadow_color_row = self._build_color_row(self.shadow_color_edit, self.shadow_color_pick_button)

        self.form = QFormLayout()
        self.form.addRow(self._label_font, self.font_family_edit)
        self.form.addRow(self._label_size, self.font_size_spin)
        self.form.addRow(self._label_color_rgba, font_color_row)
        self.form.addRow(self._blank_label_1, self.shadow_enabled_check)
        self.form.addRow(self._label_shadow_color_rgba, shadow_color_row)
        self.form.addRow(self._label_offset_seconds, self.offset_spin)
        self.form.addRow(self._label_language, self.language_combo)
        self.form.addRow(self._label_mode_preset, self.layout_preset_combo)
        self.form.addRow(self._blank_label_4, self.always_on_top_check)
        self.form.addRow(self._blank_label_2, self.click_through_check)
        self.form.addRow(self._blank_label_3, self.snap_check)

        self.save_button = QPushButton()
        self.cancel_button = QPushButton()
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.cancel_button)

        root = QVBoxLayout(self)
        root.addWidget(self.validation_label)
        root.addLayout(self.form)
        root.addLayout(buttons)

        self.save_button.clicked.connect(self._emit_save)
        self.cancel_button.clicked.connect(self.close)
        self.font_color_pick_button.clicked.connect(lambda: self._pick_color_into(self.font_color_edit))
        self.shadow_color_pick_button.clicked.connect(lambda: self._pick_color_into(self.shadow_color_edit))
        self.font_color_edit.textChanged.connect(self._clear_validation)
        self.shadow_color_edit.textChanged.connect(self._clear_validation)
        self.language_combo.currentTextChanged.connect(lambda *_: self._apply_localized_texts())
        self.layout_preset_combo.currentIndexChanged.connect(self._on_layout_preset_changed)

        self._apply_localized_texts()
        self.load_from_config(config)

    def _build_color_row(self, edit: QLineEdit, button: QPushButton):
        container = QWidget(self)
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit, 1)
        row.addWidget(button, 0)
        return container

    def _ui_language(self) -> str:
        return normalize_ui_language(self.language_combo.currentText())

    def _tr(self, key: str) -> str:
        return tr_settings_ui(self._ui_language(), key)

    def _current_preset_value(self) -> str:
        return normalize_layout_preset(str(self.layout_preset_combo.currentData() or LayoutPreset.DETAILED.value))

    def _normalized_color_text(self, value: str, fallback: str = "#FFFFFFFF") -> str:
        return normalize_rgba_hex(str(value or ""), fallback)

    def _resolved_font_color_for_preset(self, preset_value: str) -> str:
        preset_key = normalize_layout_preset(preset_value)
        draft = self._preset_font_color_drafts.get(preset_key)
        if isinstance(draft, str) and draft.strip():
            return self._normalized_color_text(draft, self._loaded_default_font_color)
        stored = self._loaded_preset_font_colors.get(preset_key)
        if isinstance(stored, str) and stored.strip():
            return self._normalized_color_text(stored, self._loaded_default_font_color)
        return self._normalized_color_text(self._loaded_default_font_color, "#FFFFFFFF")

    def _stash_current_preset_font_color(self) -> None:
        preset_key = normalize_layout_preset(self._active_preset_for_font_color)
        self._preset_font_color_drafts[preset_key] = self._normalized_color_text(
            self.font_color_edit.text().strip() or self._loaded_default_font_color,
            self._loaded_default_font_color,
        )

    def _resolved_always_on_top_for_preset(self, preset_value: str) -> bool:
        preset_key = normalize_layout_preset(preset_value)
        if preset_key in self._preset_always_on_top_drafts:
            return bool(self._preset_always_on_top_drafts[preset_key])
        if preset_key in self._loaded_preset_always_on_top:
            return bool(self._loaded_preset_always_on_top[preset_key])
        return bool(self._loaded_default_always_on_top)

    def _stash_current_preset_always_on_top(self) -> None:
        preset_key = normalize_layout_preset(self._active_preset_for_font_color)
        self._preset_always_on_top_drafts[preset_key] = bool(self.always_on_top_check.isChecked())

    def _apply_font_color_for_selected_preset(self) -> None:
        preset_key = self._current_preset_value()
        self._active_preset_for_font_color = preset_key
        self.font_color_edit.setText(self._resolved_font_color_for_preset(preset_key))
        self.always_on_top_check.setChecked(self._resolved_always_on_top_for_preset(preset_key))

    def _on_layout_preset_changed(self, *_args) -> None:
        if self._preset_switch_internal:
            return
        self._stash_current_preset_font_color()
        self._stash_current_preset_always_on_top()
        self._apply_font_color_for_selected_preset()

    def _refresh_layout_preset_combo_items(self) -> None:
        current_value = str(self.layout_preset_combo.currentData() or LayoutPreset.DETAILED.value)
        self._preset_switch_internal = True
        try:
            self.layout_preset_combo.blockSignals(True)
            self.layout_preset_combo.clear()
            self.layout_preset_combo.addItem(self._tr("preset_minimal"), LayoutPreset.MINIMAL.value)
            self.layout_preset_combo.addItem(self._tr("preset_detailed"), LayoutPreset.DETAILED.value)
            self.layout_preset_combo.addItem(self._tr("preset_context_2_2"), LayoutPreset.CONTEXT_2_2.value)
            idx = self.layout_preset_combo.findData(current_value)
            self.layout_preset_combo.setCurrentIndex(max(0, idx))
            self.layout_preset_combo.blockSignals(False)
        finally:
            self._preset_switch_internal = False

    def _apply_localized_texts(self) -> None:
        self.setWindowTitle(self._tr("window_title"))
        self._label_font.setText(self._tr("label_font"))
        self._label_size.setText(self._tr("label_size"))
        self._label_color_rgba.setText(self._tr("label_color_rgba"))
        self._label_shadow_color_rgba.setText(self._tr("label_shadow_color_rgba"))
        self._label_offset_seconds.setText(self._tr("label_offset_seconds"))
        self._label_language.setText(self._tr("label_language"))
        self._label_mode_preset.setText(self._tr("label_mode_preset"))
        self.font_color_pick_button.setText(self._tr("pick_color"))
        self.shadow_color_pick_button.setText(self._tr("pick_color"))
        self.shadow_enabled_check.setText(self._tr("shadow_enabled"))
        self.always_on_top_check.setText(self._tr("always_on_top"))
        self.click_through_check.setText(self._tr("click_through"))
        self.snap_check.setText(self._tr("snap_to_taskbar"))
        self.save_button.setText(self._tr("save"))
        self.cancel_button.setText(self._tr("close"))
        self._refresh_layout_preset_combo_items()

    def _clear_validation(self) -> None:
        self.validation_label.setText("")

    def _pick_color_into(self, target_edit: QLineEdit) -> None:
        initial = qcolor_from_rgba_hex(target_edit.text().strip() or "#FFFFFFFF", "#FFFFFFFF")
        dialog = QColorDialog(initial, self)
        dialog.setOption(QColorDialog.ShowAlphaChannel, True)
        if dialog.exec():
            chosen = dialog.currentColor()
            if chosen.isValid():
                target_edit.setText(rgba_hex_from_qcolor(chosen))

    def _parse_color(self, text: str) -> QColor | None:
        try:
            r, g, b, a = parse_rgba_hex(text)
        except ValueError:
            return None
        return QColor(r, g, b, a)

    def _color_to_hex_rgba(self, color: QColor) -> str:
        return rgba_hex_from_qcolor(color)

    def load_from_config(self, config: AppConfig) -> None:
        self._loaded_default_font_color = self._normalized_color_text(str(config.font.color), "#FFFFFFFF")
        self._loaded_preset_font_colors = {
            normalize_layout_preset(str(k)): self._normalized_color_text(str(v), self._loaded_default_font_color)
            for k, v in getattr(config.font, "preset_colors", {}).items()
            if isinstance(k, str) and isinstance(v, str)
        }
        self._preset_font_color_drafts = dict(self._loaded_preset_font_colors)
        self._loaded_default_always_on_top = bool(getattr(config.overlay, "always_on_top", True))
        self._loaded_preset_always_on_top = {
            normalize_layout_preset(str(k)): bool(v)
            for k, v in getattr(config.overlay, "always_on_top_by_preset", {}).items()
            if isinstance(k, str)
        }
        self._preset_always_on_top_drafts = dict(self._loaded_preset_always_on_top)
        self.font_family_edit.setText(str(config.font.family))
        self.font_size_spin.setValue(int(config.font.size))
        self.font_color_edit.setText(self._loaded_default_font_color)
        self.shadow_enabled_check.setChecked(bool(config.font.shadow.enabled))
        self.shadow_color_edit.setText(normalize_rgba_hex(str(config.font.shadow.color), "#000000FF"))
        self.offset_spin.setValue(float(config.lyrics.offset_seconds))
        language = str(getattr(config.lyrics, "language", "PT-BR")).upper()
        idx = self.language_combo.findText(language)
        if idx < 0:
            self.language_combo.addItem(language)
            idx = self.language_combo.findText(language)
        self.language_combo.setCurrentIndex(max(0, idx))
        self._apply_localized_texts()
        preset_value = normalize_layout_preset(getattr(config.overlay, "layout_preset", LayoutPreset.DETAILED.value))
        self._preset_switch_internal = True
        try:
            preset_idx = self.layout_preset_combo.findData(preset_value)
            self.layout_preset_combo.setCurrentIndex(max(0, preset_idx))
        finally:
            self._preset_switch_internal = False
        self._active_preset_for_font_color = preset_value
        self._apply_font_color_for_selected_preset()
        self.click_through_check.setChecked(bool(config.overlay.click_through))
        self.snap_check.setChecked(bool(config.overlay.snap_to_taskbar))

    def _emit_save(self) -> None:
        self._stash_current_preset_font_color()
        self._stash_current_preset_always_on_top()
        font_color_raw = self.font_color_edit.text().strip() or "#FFFFFFFF"
        shadow_color_raw = self.shadow_color_edit.text().strip() or "#000000FF"
        font_color = self._parse_color(font_color_raw)
        shadow_color = self._parse_color(shadow_color_raw)
        if font_color is None:
            self.validation_label.setText(self._tr("invalid_text_color"))
            return
        if shadow_color is None:
            self.validation_label.setText(self._tr("invalid_shadow_color"))
            return

        values = SettingsValues(
            font_family=self.font_family_edit.text().strip() or "Segoe UI",
            font_size=int(self.font_size_spin.value()),
            font_color=self._color_to_hex_rgba(font_color),
            shadow_enabled=bool(self.shadow_enabled_check.isChecked()),
            shadow_color=self._color_to_hex_rgba(shadow_color),
            offset_seconds=float(self.offset_spin.value()),
            language=self.language_combo.currentText().strip() or "PT-BR",
            layout_preset=str(self.layout_preset_combo.currentData() or LayoutPreset.DETAILED.value),
            always_on_top=bool(self.always_on_top_check.isChecked()),
            click_through=bool(self.click_through_check.isChecked()),
            snap_to_taskbar=bool(self.snap_check.isChecked()),
        )
        self.save_requested.emit(values)
