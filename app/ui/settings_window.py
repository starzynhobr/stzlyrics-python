from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
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
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.i18n import normalize_ui_language, tr_settings_ui
from app.layout_presets import ContextAnimationStyle, LayoutPreset, normalize_context_animation_style, normalize_layout_preset
from app.ui.color_utils import normalize_rgba_hex, parse_rgba_hex, qcolor_from_rgba_hex, rgba_hex_from_qcolor
from app.ui.app_icon import load_app_icon


SUPPORTED_LANGUAGES = ["EN", "PT-BR", "ES", "IT", "DE", "FR", "JP"]


def _draw_chevron(widget: QWidget, center_x: float, center_y: float, upward: bool = False) -> None:
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#cbd5e1"), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    direction = -1 if upward else 1
    painter.drawPolyline(QPolygonF([
        QPointF(center_x - 4, center_y - 2 * direction),
        QPointF(center_x, center_y + 2 * direction),
        QPointF(center_x + 4, center_y - 2 * direction),
    ]))


def _set_dark_windows_title_bar(hwnd: int) -> None:
    if sys.platform != "win32":
        return
    try:
        dwm = ctypes.WinDLL("dwmapi")
        set_attribute = dwm.DwmSetWindowAttribute
        set_attribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        set_attribute.restype = ctypes.c_long
        for attribute, color in ((35, 0x00271811), (36, 0x00EBE7E5)):
            value = ctypes.c_uint(color)
            set_attribute(ctypes.c_void_p(hwnd), attribute, ctypes.byref(value), ctypes.sizeof(value))
    except (OSError, AttributeError):
        pass


class _NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        _draw_chevron(self, self.width() - 14, self.height() * 0.31, upward=True)
        _draw_chevron(self, self.width() - 14, self.height() * 0.70)


class _NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        _draw_chevron(self, self.width() - 14, self.height() * 0.31, upward=True)
        _draw_chevron(self, self.width() - 14, self.height() * 0.70)


class _NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        _draw_chevron(self, self.width() - 16, self.height() / 2)


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
    context_animation_style: str
    start_with_windows: bool
    always_on_top: bool
    click_through: bool
    snap_to_taskbar: bool


class SettingsWindow(QDialog):
    save_requested = Signal(object)  # SettingsValues
    clear_cache_requested = Signal()

    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowIcon(load_app_icon())
        self.setModal(False)
        self.resize(620, 440)
        self.setMinimumSize(550, 400)
        self._preset_font_color_drafts: dict[str, str] = {}
        self._loaded_preset_font_colors: dict[str, str] = {}
        self._loaded_default_font_color = "#FFFFFFFF"
        self._active_preset_for_font_color = LayoutPreset.DETAILED.value
        self._preset_always_on_top_drafts: dict[str, bool] = {}
        self._loaded_preset_always_on_top: dict[str, bool] = {}
        self._loaded_default_always_on_top = True
        self._preset_switch_internal = False
        self._save_confirmed = False

        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: #ff8080;")
        self.validation_label.setWordWrap(True)
        self.validation_label.hide()

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
        self.context_anim_style_combo = _NoWheelComboBox()

        self.always_on_top_check = QCheckBox()
        self.start_with_windows_check = QCheckBox()
        self.click_through_check = QCheckBox()
        self.snap_check = QCheckBox()

        self._label_font = QLabel("")
        self._label_size = QLabel("")
        self._label_color_rgba = QLabel("")
        self._label_shadow_color_rgba = QLabel("")
        self._label_offset_seconds = QLabel("")
        self._label_language = QLabel("")
        self._label_mode_preset = QLabel("")
        self._label_context_animation = QLabel("")
        self._blank_label_1 = QLabel("")
        self._blank_label_2 = QLabel("")
        self._blank_label_3 = QLabel("")
        self._blank_label_4 = QLabel("")
        self._blank_label_5 = QLabel("")

        font_color_row = self._build_color_row(self.font_color_edit, self.font_color_pick_button)
        shadow_color_row = self._build_color_row(self.shadow_color_edit, self.shadow_color_pick_button)

        self.tabs = QTabWidget(self)
        self.appearance_tab = QWidget(self)
        self.mode_tab = QWidget(self)
        self.general_tab = QWidget(self)
        self.appearance_form = QFormLayout(self.appearance_tab)
        self.mode_form = QFormLayout(self.mode_tab)
        self.general_form = QFormLayout(self.general_tab)
        for form in (self.appearance_form, self.mode_form, self.general_form):
            form.setContentsMargins(24, 24, 24, 24)
            form.setHorizontalSpacing(20)
            form.setVerticalSpacing(16)

        self.appearance_form.addRow(self._label_font, self.font_family_edit)
        self.appearance_form.addRow(self._label_size, self.font_size_spin)
        self.appearance_form.addRow(self._label_color_rgba, font_color_row)
        self.appearance_form.addRow(self._blank_label_1, self.shadow_enabled_check)
        self.appearance_form.addRow(self._label_shadow_color_rgba, shadow_color_row)
        self.mode_form.addRow(self._label_mode_preset, self.layout_preset_combo)
        self.mode_form.addRow(self._label_context_animation, self.context_anim_style_combo)
        self.mode_form.addRow(self._blank_label_4, self.always_on_top_check)
        self.mode_form.addRow(self._blank_label_2, self.click_through_check)
        self.mode_form.addRow(self._blank_label_3, self.snap_check)
        self.general_form.addRow(self._label_offset_seconds, self.offset_spin)
        self.general_form.addRow(self._label_language, self.language_combo)
        self.general_form.addRow(self._blank_label_5, self.start_with_windows_check)
        self.tabs.addTab(self.appearance_tab, "")
        self.tabs.addTab(self.mode_tab, "")
        self.tabs.addTab(self.general_tab, "")
        self.tabs.tabBar().setCursor(Qt.PointingHandCursor)

        self.save_button = QPushButton()
        self.cancel_button = QPushButton()
        self.clear_cache_button = QPushButton()
        for widget in (
            self.font_color_pick_button, self.shadow_color_pick_button,
            self.shadow_enabled_check, self.always_on_top_check, self.start_with_windows_check,
            self.click_through_check, self.snap_check, self.language_combo,
            self.layout_preset_combo, self.context_anim_style_combo,
            self.font_size_spin, self.offset_spin,
            self.save_button, self.cancel_button, self.clear_cache_button,
        ):
            widget.setCursor(Qt.PointingHandCursor)
        buttons = QHBoxLayout()
        buttons.addWidget(self.clear_cache_button)
        buttons.addStretch(1)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.cancel_button)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)
        root.addWidget(self.validation_label)
        root.addWidget(self.tabs, 1)
        root.addLayout(buttons)

        self.setStyleSheet("""
            QDialog { background: #111827; color: #e5e7eb; font-size: 13px; }
            QLabel, QCheckBox { color: #e5e7eb; }
            QTabWidget::pane { border: 1px solid #334155; border-radius: 10px;
                               border-top-left-radius: 0px; background: #1e293b; }
            QTabBar::tab { background: #172033; color: #94a3b8; padding: 11px 20px;
                           border: 1px solid #334155; border-bottom: none;
                           border-top-left-radius: 8px; border-top-right-radius: 8px;
                           margin-right: 2px; }
            QTabBar::tab:selected { background: #1e293b; color: #f8fafc;
                                    border-top: 2px solid #60a5fa; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background: #0f172a; color: #f8fafc; border: 1px solid #475569;
                border-radius: 6px; min-height: 30px; padding: 2px 9px;
                selection-background-color: #2563eb;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border: 1px solid #60a5fa;
            }
            QComboBox QAbstractItemView { background: #1e293b; color: #f8fafc;
                                         selection-background-color: #2563eb; }
            QComboBox::drop-down { width: 32px; border: none; background: transparent; }
            QComboBox::down-arrow { image: none; width: 0px; height: 0px; }
            QSpinBox::up-button, QSpinBox::down-button,
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 26px; border: none; background: transparent;
            }
            QSpinBox::up-arrow, QSpinBox::down-arrow,
            QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {
                image: none; width: 0px; height: 0px;
            }
            QPushButton { background: #334155; color: #f8fafc; border: 1px solid #475569;
                          border-radius: 6px; min-height: 32px; padding: 2px 14px; }
            QPushButton:hover { background: #475569; }
            QPushButton:focus { border: 1px solid #93c5fd; }
        """)
        self.save_button.setStyleSheet("background: #2563eb; border-color: #3b82f6;")

        self.save_button.clicked.connect(self._emit_save)
        self.cancel_button.clicked.connect(self.close)
        self.clear_cache_button.clicked.connect(self._confirm_clear_cache)
        self.font_color_pick_button.clicked.connect(lambda: self._pick_color_into(self.font_color_edit))
        self.shadow_color_pick_button.clicked.connect(lambda: self._pick_color_into(self.shadow_color_edit))
        self.font_color_edit.textChanged.connect(self._clear_validation)
        self.shadow_color_edit.textChanged.connect(self._clear_validation)
        self.language_combo.currentTextChanged.connect(lambda *_: self._apply_localized_texts())
        self.layout_preset_combo.currentIndexChanged.connect(self._on_layout_preset_changed)
        for field in (self.font_family_edit, self.font_color_edit, self.shadow_color_edit):
            field.textChanged.connect(self._mark_dirty)
        for field in (self.font_size_spin, self.offset_spin):
            field.valueChanged.connect(self._mark_dirty)
        for field in (self.language_combo, self.layout_preset_combo, self.context_anim_style_combo):
            field.currentIndexChanged.connect(self._mark_dirty)
        for field in (
            self.shadow_enabled_check, self.always_on_top_check, self.start_with_windows_check,
            self.click_through_check, self.snap_check,
        ):
            field.toggled.connect(self._mark_dirty)

        self._apply_localized_texts()
        self.load_from_config(config)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        _set_dark_windows_title_bar(int(self.winId()))

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
        self._sync_context_animation_visibility()

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

    def _refresh_context_anim_style_combo_items(self) -> None:
        current_value = str(self.context_anim_style_combo.currentData() or ContextAnimationStyle.SLIDE.value)
        self.context_anim_style_combo.blockSignals(True)
        self.context_anim_style_combo.clear()
        self.context_anim_style_combo.addItem(self._tr("anim_style_slide"), ContextAnimationStyle.SLIDE.value)
        self.context_anim_style_combo.addItem(self._tr("anim_style_slide_fade"), ContextAnimationStyle.SLIDE_FADE.value)
        self.context_anim_style_combo.addItem(self._tr("anim_style_fade"), ContextAnimationStyle.FADE.value)
        self.context_anim_style_combo.addItem(self._tr("anim_style_none"), ContextAnimationStyle.NONE.value)
        idx = self.context_anim_style_combo.findData(normalize_context_animation_style(current_value))
        self.context_anim_style_combo.setCurrentIndex(max(0, idx))
        self.context_anim_style_combo.blockSignals(False)

    def _sync_context_animation_visibility(self) -> None:
        is_context_preset = self._current_preset_value() == LayoutPreset.CONTEXT_2_2.value
        self._label_context_animation.setVisible(is_context_preset)
        self.context_anim_style_combo.setVisible(is_context_preset)

    def _apply_localized_texts(self) -> None:
        self.setWindowTitle(self._tr("window_title"))
        self.tabs.setTabText(0, self._tr("tab_appearance"))
        self.tabs.setTabText(1, self._tr("tab_mode"))
        self.tabs.setTabText(2, self._tr("tab_general"))
        self._label_font.setText(self._tr("label_font"))
        self._label_size.setText(self._tr("label_size"))
        self._label_color_rgba.setText(self._tr("label_color_rgba"))
        self._label_shadow_color_rgba.setText(self._tr("label_shadow_color_rgba"))
        self._label_offset_seconds.setText(self._tr("label_offset_seconds"))
        offset_tooltip = self._tr("offset_tooltip")
        self._label_offset_seconds.setToolTip(offset_tooltip)
        self.offset_spin.setToolTip(offset_tooltip)
        self._label_language.setText(self._tr("label_language"))
        self._label_mode_preset.setText(self._tr("label_mode_preset"))
        self._label_context_animation.setText(self._tr("label_context_animation"))
        self.font_color_pick_button.setText(self._tr("pick_color"))
        self.shadow_color_pick_button.setText(self._tr("pick_color"))
        self.shadow_enabled_check.setText(self._tr("shadow_enabled"))
        self.always_on_top_check.setText(self._tr("always_on_top"))
        self.start_with_windows_check.setText(self._tr("start_with_windows"))
        self.click_through_check.setText(self._tr("click_through"))
        self.snap_check.setText(self._tr("snap_to_taskbar"))
        self.clear_cache_button.setText(self._tr("clear_local_cache"))
        self.save_button.setText(self._tr("saved" if self._save_confirmed else "save"))
        self.cancel_button.setText(self._tr("close"))
        self._refresh_layout_preset_combo_items()
        self._refresh_context_anim_style_combo_items()
        self._sync_context_animation_visibility()

    def _clear_validation(self) -> None:
        self.validation_label.setText("")
        self.validation_label.hide()

    def _mark_dirty(self, *_args) -> None:
        if self._save_confirmed:
            self._save_confirmed = False
            self.save_button.setText(self._tr("save"))

    def mark_saved(self) -> None:
        self._save_confirmed = True
        self.save_button.setText(self._tr("saved"))

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

    def _confirm_clear_cache(self) -> None:
        answer = QMessageBox.warning(
            self,
            self._tr("clear_local_cache_title"),
            self._tr("clear_local_cache_confirm"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.clear_cache_requested.emit()

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
        anim_style = normalize_context_animation_style(getattr(config.overlay, "context_animation_style", "slide"))
        anim_idx = self.context_anim_style_combo.findData(anim_style)
        self.context_anim_style_combo.setCurrentIndex(max(0, anim_idx))
        self._sync_context_animation_visibility()
        self.start_with_windows_check.setChecked(bool(getattr(config.overlay, "start_with_windows", False)))
        self.click_through_check.setChecked(bool(config.overlay.click_through))
        self.snap_check.setChecked(bool(config.overlay.snap_to_taskbar))
        self._save_confirmed = False
        self.save_button.setText(self._tr("save"))

    def _emit_save(self) -> None:
        self._stash_current_preset_font_color()
        self._stash_current_preset_always_on_top()
        font_color_raw = self.font_color_edit.text().strip() or "#FFFFFFFF"
        shadow_color_raw = self.shadow_color_edit.text().strip() or "#000000FF"
        font_color = self._parse_color(font_color_raw)
        shadow_color = self._parse_color(shadow_color_raw)
        if font_color is None:
            self.validation_label.setText(self._tr("invalid_text_color"))
            self.validation_label.show()
            return
        if shadow_color is None:
            self.validation_label.setText(self._tr("invalid_shadow_color"))
            self.validation_label.show()
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
            context_animation_style=normalize_context_animation_style(
                str(self.context_anim_style_combo.currentData() or ContextAnimationStyle.SLIDE.value)
            ),
            start_with_windows=bool(self.start_with_windows_check.isChecked()),
            always_on_top=bool(self.always_on_top_check.isChecked()),
            click_through=bool(self.click_through_check.isChecked()),
            snap_to_taskbar=bool(self.snap_check.isChecked()),
        )
        self.save_requested.emit(values)
