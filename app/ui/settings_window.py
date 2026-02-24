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
        self.setWindowTitle("Configurações - STZLyrics Overlay")
        self.setModal(False)
        self.setMinimumWidth(420)

        self.info_label = QLabel("Cores em formato Qt: #RRGGBB ou #RRGGBBAA")
        self.info_label.setWordWrap(True)
        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: #ff8080;")
        self.validation_label.setWordWrap(True)

        self.font_family_edit = QLineEdit()
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 96)

        self.font_color_edit = QLineEdit()
        self.font_color_pick_button = QPushButton("Selecionar...")
        self.shadow_enabled_check = QCheckBox("Ativar sombra")
        self.shadow_color_edit = QLineEdit()
        self.shadow_color_pick_button = QPushButton("Selecionar...")
        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setRange(-30.0, 30.0)
        self.offset_spin.setDecimals(2)
        self.offset_spin.setSingleStep(0.05)

        self.language_combo = QComboBox()
        self.language_combo.addItems(SUPPORTED_LANGUAGES)
        self.layout_preset_combo = QComboBox()
        self.layout_preset_combo.addItem("Mínimo", LayoutPreset.MINIMAL.value)
        self.layout_preset_combo.addItem("Detalhado", LayoutPreset.DETAILED.value)

        self.click_through_check = QCheckBox("Click-through")
        self.snap_check = QCheckBox("Snap na taskbar/borda")

        font_color_row = self._build_color_row(self.font_color_edit, self.font_color_pick_button)
        shadow_color_row = self._build_color_row(self.shadow_color_edit, self.shadow_color_pick_button)

        form = QFormLayout()
        form.addRow("Fonte", self.font_family_edit)
        form.addRow("Tamanho", self.font_size_spin)
        form.addRow("Cor RGBA", font_color_row)
        form.addRow("", self.shadow_enabled_check)
        form.addRow("Cor sombra RGBA", shadow_color_row)
        form.addRow("Offset (seg)", self.offset_spin)
        form.addRow("Idioma", self.language_combo)
        form.addRow("Modo / Preset", self.layout_preset_combo)
        form.addRow("", self.click_through_check)
        form.addRow("", self.snap_check)

        self.save_button = QPushButton("Salvar")
        self.cancel_button = QPushButton("Fechar")
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.cancel_button)

        root = QVBoxLayout(self)
        root.addWidget(self.info_label)
        root.addWidget(self.validation_label)
        root.addLayout(form)
        root.addLayout(buttons)

        self.save_button.clicked.connect(self._emit_save)
        self.cancel_button.clicked.connect(self.close)
        self.font_color_pick_button.clicked.connect(lambda: self._pick_color_into(self.font_color_edit))
        self.shadow_color_pick_button.clicked.connect(lambda: self._pick_color_into(self.shadow_color_edit))
        self.font_color_edit.textChanged.connect(self._clear_validation)
        self.shadow_color_edit.textChanged.connect(self._clear_validation)

        self.load_from_config(config)

    def _build_color_row(self, edit: QLineEdit, button: QPushButton):
        container = QWidget(self)
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit, 1)
        row.addWidget(button, 0)
        return container

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
            self.validation_label.setText("Cor RGBA inválida para o texto.")
            return
        if shadow_color is None:
            self.validation_label.setText("Cor RGBA inválida para a sombra.")
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
