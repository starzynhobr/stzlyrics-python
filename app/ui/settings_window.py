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
from app.layout_presets import LayoutPreset, normalize_layout_preset
from app.ui.color_utils import normalize_rgba_hex, parse_rgba_hex, qcolor_from_rgba_hex, rgba_hex_from_qcolor


SUPPORTED_LANGUAGES = ["EN", "PT-BR", "ES", "IT", "DE", "FR", "JP"]

UI_STRINGS: dict[str, dict[str, str]] = {
    "PT-BR": {
        "window_title": "Configurações - STZLyrics Overlay",
        "label_font": "Fonte",
        "label_size": "Tamanho",
        "label_color_rgba": "Cor RGBA",
        "label_shadow_color_rgba": "Cor sombra RGBA",
        "label_offset_seconds": "Offset (seg)",
        "label_language": "Idioma",
        "label_mode_preset": "Modo / Preset",
        "pick_color": "Selecionar...",
        "shadow_enabled": "Ativar sombra",
        "click_through": "Clicar Através",
        "snap_to_taskbar": "Snap na taskbar/borda",
        "save": "Salvar",
        "close": "Fechar",
        "preset_minimal": "Mínimo",
        "preset_detailed": "Detalhado",
        "invalid_text_color": "Cor RGBA inválida para o texto.",
        "invalid_shadow_color": "Cor RGBA inválida para a sombra.",
    },
    "EN": {
        "window_title": "Settings - STZLyrics Overlay",
        "label_font": "Font",
        "label_size": "Size",
        "label_color_rgba": "Color RGBA",
        "label_shadow_color_rgba": "Shadow Color RGBA",
        "label_offset_seconds": "Offset (sec)",
        "label_language": "Language",
        "label_mode_preset": "Mode / Preset",
        "pick_color": "Select...",
        "shadow_enabled": "Enable shadow",
        "click_through": "Click-through",
        "snap_to_taskbar": "Snap to taskbar/edge",
        "save": "Save",
        "close": "Close",
        "preset_minimal": "Minimal",
        "preset_detailed": "Detailed",
        "invalid_text_color": "Invalid RGBA color for text.",
        "invalid_shadow_color": "Invalid RGBA color for shadow.",
    },
    "ES": {
        "window_title": "Configuración - STZLyrics Overlay",
        "label_font": "Fuente",
        "label_size": "Tamaño",
        "label_color_rgba": "Color RGBA",
        "label_shadow_color_rgba": "Color de sombra RGBA",
        "label_offset_seconds": "Offset (seg)",
        "label_language": "Idioma",
        "label_mode_preset": "Modo / Preajuste",
        "pick_color": "Seleccionar...",
        "shadow_enabled": "Activar sombra",
        "click_through": "Clic a través",
        "snap_to_taskbar": "Ajustar a la barra/borde",
        "save": "Guardar",
        "close": "Cerrar",
        "preset_minimal": "Mínimo",
        "preset_detailed": "Detallado",
        "invalid_text_color": "Color RGBA inválido para el texto.",
        "invalid_shadow_color": "Color RGBA inválido para la sombra.",
    },
    "IT": {
        "window_title": "Impostazioni - STZLyrics Overlay",
        "label_font": "Carattere",
        "label_size": "Dimensione",
        "label_color_rgba": "Colore RGBA",
        "label_shadow_color_rgba": "Colore ombra RGBA",
        "label_offset_seconds": "Offset (sec)",
        "label_language": "Lingua",
        "label_mode_preset": "Modalità / Preset",
        "pick_color": "Seleziona...",
        "shadow_enabled": "Attiva ombra",
        "click_through": "Clic attraverso",
        "snap_to_taskbar": "Aggancia a taskbar/bordo",
        "save": "Salva",
        "close": "Chiudi",
        "preset_minimal": "Minimo",
        "preset_detailed": "Dettagliato",
        "invalid_text_color": "Colore RGBA non valido per il testo.",
        "invalid_shadow_color": "Colore RGBA non valido per l'ombra.",
    },
    "DE": {
        "window_title": "Einstellungen - STZLyrics Overlay",
        "label_font": "Schriftart",
        "label_size": "Größe",
        "label_color_rgba": "RGBA-Farbe",
        "label_shadow_color_rgba": "Schattenfarbe RGBA",
        "label_offset_seconds": "Offset (Sek)",
        "label_language": "Sprache",
        "label_mode_preset": "Modus / Preset",
        "pick_color": "Auswählen...",
        "shadow_enabled": "Schatten aktivieren",
        "click_through": "Durchklicken",
        "snap_to_taskbar": "An Taskleiste/Rand einrasten",
        "save": "Speichern",
        "close": "Schließen",
        "preset_minimal": "Minimal",
        "preset_detailed": "Detailliert",
        "invalid_text_color": "Ungültige RGBA-Farbe für den Text.",
        "invalid_shadow_color": "Ungültige RGBA-Farbe für den Schatten.",
    },
    "FR": {
        "window_title": "Paramètres - STZLyrics Overlay",
        "label_font": "Police",
        "label_size": "Taille",
        "label_color_rgba": "Couleur RGBA",
        "label_shadow_color_rgba": "Couleur d'ombre RGBA",
        "label_offset_seconds": "Offset (sec)",
        "label_language": "Langue",
        "label_mode_preset": "Mode / Préréglage",
        "pick_color": "Sélectionner...",
        "shadow_enabled": "Activer l'ombre",
        "click_through": "Clic à travers",
        "snap_to_taskbar": "Aimanter à la barre/bord",
        "save": "Enregistrer",
        "close": "Fermer",
        "preset_minimal": "Minimal",
        "preset_detailed": "Détaillé",
        "invalid_text_color": "Couleur RGBA invalide pour le texte.",
        "invalid_shadow_color": "Couleur RGBA invalide pour l'ombre.",
    },
    "JP": {
        "window_title": "設定 - STZLyrics Overlay",
        "label_font": "フォント",
        "label_size": "サイズ",
        "label_color_rgba": "色 RGBA",
        "label_shadow_color_rgba": "影の色 RGBA",
        "label_offset_seconds": "オフセット (秒)",
        "label_language": "言語",
        "label_mode_preset": "モード / プリセット",
        "pick_color": "選択...",
        "shadow_enabled": "影を有効化",
        "click_through": "クリック透過",
        "snap_to_taskbar": "タスクバー/端にスナップ",
        "save": "保存",
        "close": "閉じる",
        "preset_minimal": "最小",
        "preset_detailed": "詳細",
        "invalid_text_color": "テキストのRGBA色が無効です。",
        "invalid_shadow_color": "影のRGBA色が無効です。",
    },
}


class _NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class _NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class _NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


def _resolve_ui_language(language_code: str) -> str:
    code = (language_code or "").strip().upper()
    if code in UI_STRINGS:
        return code
    if code.startswith("PT"):
        return "PT-BR"
    if code.startswith("EN"):
        return "EN"
    return "EN"


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
    click_through: bool
    snap_to_taskbar: bool


class SettingsWindow(QDialog):
    save_requested = Signal(object)  # SettingsValues

    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.setModal(False)
        self.setMinimumWidth(420)

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
        return _resolve_ui_language(self.language_combo.currentText())

    def _tr(self, key: str) -> str:
        lang = self._ui_language()
        if key in UI_STRINGS.get(lang, {}):
            return UI_STRINGS[lang][key]
        return UI_STRINGS["EN"].get(key, key)

    def _refresh_layout_preset_combo_items(self) -> None:
        current_value = str(self.layout_preset_combo.currentData() or LayoutPreset.DETAILED.value)
        self.layout_preset_combo.blockSignals(True)
        self.layout_preset_combo.clear()
        self.layout_preset_combo.addItem(self._tr("preset_minimal"), LayoutPreset.MINIMAL.value)
        self.layout_preset_combo.addItem(self._tr("preset_detailed"), LayoutPreset.DETAILED.value)
        idx = self.layout_preset_combo.findData(current_value)
        self.layout_preset_combo.setCurrentIndex(max(0, idx))
        self.layout_preset_combo.blockSignals(False)

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
        self.font_family_edit.setText(str(config.font.family))
        self.font_size_spin.setValue(int(config.font.size))
        self.font_color_edit.setText(normalize_rgba_hex(str(config.font.color), "#FFFFFFFF"))
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
        preset_idx = self.layout_preset_combo.findData(preset_value)
        self.layout_preset_combo.setCurrentIndex(max(0, preset_idx))
        self.click_through_check.setChecked(bool(config.overlay.click_through))
        self.snap_check.setChecked(bool(config.overlay.snap_to_taskbar))

    def _emit_save(self) -> None:
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
            click_through=bool(self.click_through_check.isChecked()),
            snap_to_taskbar=bool(self.snap_check.isChecked()),
        )
        self.save_requested.emit(values)
