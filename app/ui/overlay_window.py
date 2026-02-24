from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QMouseEvent, QPainter
from PySide6.QtWidgets import QWidget

from app.config import AppConfig
from app.layout_presets import build_layout_render_model
from app.ui.color_utils import qcolor_from_rgba_hex
from app.ui.windows_api import WinRect, set_click_through, set_window_topmost, snap_position


logger = logging.getLogger("stzlyrics_overlay.overlay")


def _format_time(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _safe_color(color_str: str, fallback: str) -> QColor:
    return qcolor_from_rgba_hex(color_str, fallback)


@dataclass(slots=True)
class PositionPayload:
    x: int
    y: int
    screen_name: str
    scale_percent: int
    screen_width: int
    screen_height: int


class OverlayWindow(QWidget):
    position_committed = Signal(object)  # PositionPayload

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        flags = Qt.FramelessWindowHint | Qt.Tool
        if config.overlay.always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        super().__init__(parent, flags)

        self._config = config
        self._track_text = "Aguardando mídia..."
        self._lyric_text = "Conectando ao GSMTC..."
        self._status_hint = ""
        self._clock_debug_text = ""
        self._track_base_text = "Aguardando mídia..."
        self._click_through = bool(config.overlay.click_through)
        self._snap_enabled = bool(config.overlay.snap_to_taskbar)
        self._dragging = False
        self._drag_offset = QPoint()
        self._track_color = QColor(200, 200, 200, 255)
        self._lyric_color = QColor(255, 255, 255, 255)
        self._shadow_color = QColor(0, 0, 0, 255)
        self._layout_model = build_layout_render_model("detailed")
        self._debug_clock_overlay_enabled = False
        self._always_on_top_enabled = bool(config.overlay.always_on_top)
        self._topmost_guard_timer = QTimer(self)
        self._topmost_guard_timer.setInterval(250)
        self._topmost_guard_timer.timeout.connect(self._topmost_guard_tick)

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.apply_config(config)

    def apply_config(self, config: AppConfig) -> None:
        self._config = config
        self._click_through = bool(config.overlay.click_through)
        self._snap_enabled = bool(config.overlay.snap_to_taskbar)
        self._always_on_top_enabled = bool(config.overlay.always_on_top)
        self.apply_layout_preset(getattr(self._config.overlay, "layout_preset", "detailed"))
        self._debug_clock_overlay_enabled = bool(getattr(self._config.clock, "debug_clock_overlay", False))
        self._track_color = _safe_color(self._config.font.track_color, "#C8C8C8FF")
        self._lyric_color = _safe_color(self._config.font.color, "#FFFFFFFF")
        self._shadow_color = _safe_color(self._config.font.shadow.color, "#000000FF")
        self._log_color_application()
        self.resize(int(config.overlay.width), int(config.overlay.height))
        self.update()
        self.apply_click_through()
        self._ensure_topmost_if_needed()
        self._sync_topmost_guard_timer()

    def apply_layout_preset(self, preset: str) -> None:
        self._layout_model = build_layout_render_model(preset)
        logger.info("Applying layout preset preset=%s", self._layout_model.preset.value)
        self.update()

    def _log_color_application(self) -> None:
        logger.info(
            "Applying overlay colors text_rgba=(%s,%s,%s,%s) track_rgba=(%s,%s,%s,%s) shadow_rgba=(%s,%s,%s,%s) shadow_enabled=%s",
            self._lyric_color.red(),
            self._lyric_color.green(),
            self._lyric_color.blue(),
            self._lyric_color.alpha(),
            self._track_color.red(),
            self._track_color.green(),
            self._track_color.blue(),
            self._track_color.alpha(),
            self._shadow_color.red(),
            self._shadow_color.green(),
            self._shadow_color.blue(),
            self._shadow_color.alpha(),
            bool(self._config.font.shadow.enabled),
        )
        if self._lyric_color.alpha() == 0:
            logger.warning("Overlay lyric text alpha is 0 (fully transparent)")
        if self._config.font.shadow.enabled and self._shadow_color.alpha() == 0:
            logger.warning("Overlay shadow alpha is 0 (fully transparent)")

    def set_track_state(
        self,
        artist: str,
        title: str,
        position_seconds: float,
        duration_seconds: float,
        is_playing: bool,
        source_app: str = "",
    ) -> None:
        track = f"{artist} - {title}".strip(" -")
        pos = _format_time(position_seconds)
        dur = _format_time(duration_seconds) if duration_seconds > 0 else "--:--"
        source_suffix = f" | {source_app}" if source_app else ""
        play_prefix = ">" if is_playing else "||"
        self._track_base_text = f"{play_prefix} {track or 'Sem faixa ativa'}  [{pos} / {dur}]{source_suffix}"
        self._rebuild_track_text()
        self.update()

    def set_lyric_text(self, text: str) -> None:
        self._lyric_text = (text or "").strip()
        self.update()

    def set_status_hint(self, text: str) -> None:
        self._status_hint = (text or "").strip()
        self._rebuild_track_text()
        self.update()

    def set_clock_debug_text(self, text: str) -> None:
        self._clock_debug_text = (text or "").strip()
        self._rebuild_track_text()
        self.update()

    def _rebuild_track_text(self) -> None:
        base = self._track_base_text
        if self._status_hint:
            base = f"{base} | {self._status_hint}"
        if (
            self._debug_clock_overlay_enabled
            and self._layout_model.show_header
            and self._clock_debug_text
        ):
            base = f"{base} | {self._clock_debug_text}"
        self._track_text = base

    def set_click_through_enabled(self, enabled: bool) -> None:
        self._click_through = bool(enabled)
        self.apply_click_through()
        self.update()

    def set_snap_enabled(self, enabled: bool) -> None:
        self._snap_enabled = bool(enabled)

    def apply_click_through(self) -> None:
        try:
            hwnd = int(self.winId())
        except Exception:
            hwnd = 0
        set_click_through(hwnd, self._click_through)
        self._ensure_topmost_if_needed()

    def _ensure_topmost_if_needed(self) -> None:
        if not self._always_on_top_enabled:
            return
        if not self.isVisible():
            return
        try:
            hwnd = int(self.winId())
        except Exception:
            hwnd = 0
        # Force a z-order "bump" so the window is reinserted at the top of the
        # topmost stack after shell/taskbar interactions.
        self.raise_()
        set_window_topmost(hwnd, True, force_reorder=True)

    def _topmost_guard_tick(self) -> None:
        self._ensure_topmost_if_needed()

    def _sync_topmost_guard_timer(self) -> None:
        should_run = self._always_on_top_enabled and self.isVisible()
        if should_run and (not self._topmost_guard_timer.isActive()):
            self._topmost_guard_timer.start()
        if (not should_run) and self._topmost_guard_timer.isActive():
            self._topmost_guard_timer.stop()

    def move_default_near_taskbar(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.left() + max(0, (geo.width() - self.width()) // 2)
        y = geo.bottom() - self.height() - 2
        self.move(x, y)

    def restore_position(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.geometry()
        scale_percent = self._screen_scale_percent(screen)
        saved = self._config.get_saved_position(
            screen.name(),
            scale_percent,
            geo.width(),
            geo.height(),
        )
        if saved is None:
            self.move_default_near_taskbar()
            return
        self.move(saved[0], saved[1])
        self._clamp_to_visible()

    def _current_screen(self):
        center = self.frameGeometry().center()
        return QGuiApplication.screenAt(center) or self.screen() or QGuiApplication.primaryScreen()

    def _screen_scale_percent(self, screen) -> int:
        try:
            return int(round((screen.logicalDotsPerInch() / 96.0) * 100))
        except Exception:
            return 100

    def _clamp_to_visible(self) -> None:
        screen = self._current_screen()
        if screen is None:
            return
        # Clamp to the monitor while allowing controlled overflow equal to the
        # taskbar-reserved thickness on this screen. This preserves positions
        # intentionally placed a few pixels "into" the taskbar/off-screen and
        # scales automatically for different resolutions/DPI/taskbar sizes.
        geo = screen.geometry()
        avail = screen.availableGeometry()
        left_overflow = max(0, avail.left() - geo.left())
        top_overflow = max(0, avail.top() - geo.top())
        right_overflow = max(0, geo.right() - avail.right())
        bottom_overflow = max(0, geo.bottom() - avail.bottom())
        min_x = geo.left() - left_overflow
        min_y = geo.top() - top_overflow
        max_x = max(min_x, (geo.right() + 1) - self.width() + right_overflow)
        max_y = max(min_y, (geo.bottom() + 1) - self.height() + bottom_overflow)
        x = min(max(self.x(), min_x), max_x)
        y = min(max(self.y(), min_y), max_y)
        self.move(x, y)

    def _build_position_payload(self) -> PositionPayload | None:
        screen = self._current_screen()
        if screen is None:
            return None
        geo = screen.geometry()
        return PositionPayload(
            x=int(self.x()),
            y=int(self.y()),
            screen_name=screen.name(),
            scale_percent=self._screen_scale_percent(screen),
            screen_width=geo.width(),
            screen_height=geo.height(),
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._click_through:
            event.ignore()
            return
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._dragging or self._click_through:
            super().mouseMoveEvent(event)
            return

        candidate = event.globalPosition().toPoint() - self._drag_offset
        x, y = candidate.x(), candidate.y()
        screen = QGuiApplication.screenAt(event.globalPosition().toPoint()) or self._current_screen()
        if self._snap_enabled and screen is not None:
            geo = screen.availableGeometry()
            x, y = snap_position(
                x=x,
                y=y,
                width=self.width(),
                height=self.height(),
                screen_rect=WinRect(geo.left(), geo.top(), geo.right() + 1, geo.bottom() + 1),
                threshold=self._config.overlay.snap_threshold,
            )
        self.move(int(x), int(y))
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            payload = self._build_position_payload()
            if payload is not None:
                self.position_committed.emit(payload)
            self._ensure_topmost_if_needed()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.apply_click_through()
        self._sync_topmost_guard_timer()
        self._ensure_topmost_if_needed()
        QTimer.singleShot(100, self._ensure_topmost_if_needed)

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        self._sync_topmost_guard_timer()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        pad_x = int(self._config.overlay.padding_x)
        pad_y = int(self._config.overlay.padding_y)
        content = QRect(
            pad_x,
            pad_y,
            max(0, self.width() - (pad_x * 2)),
            max(0, self.height() - (pad_y * 2)),
        )
        header_height = self._layout_model.header_height
        header_gap = self._layout_model.header_gap if self._layout_model.show_header else 0
        track_rect = QRect(content.left(), content.top(), content.width(), header_height)
        lyric_y = content.top() + header_height + header_gap
        lyric_rect = QRect(
            content.left(),
            lyric_y,
            content.width(),
            max(0, content.height() - (header_height + header_gap)),
        )

        if not self._click_through:
            painter.setPen(QColor(255, 255, 255, 40))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)

        track_font = QFont(self._config.font.family, int(self._config.font.track_size))
        lyric_font = QFont(self._config.font.family, int(self._config.font.size))

        if self._layout_model.show_header and track_rect.height() > 0:
            self._draw_text(
                painter,
                rect=track_rect,
                text=self._elide(track_font, self._track_text, track_rect.width()),
                font=track_font,
                color=self._track_color,
            )
        self._draw_text(
            painter,
            rect=lyric_rect,
            text=self._elide(lyric_font, self._lyric_text, lyric_rect.width()),
            font=lyric_font,
            color=self._lyric_color,
        )

    def _elide(self, font: QFont, text: str, width: int) -> str:
        return QFontMetrics(font).elidedText(text, Qt.ElideRight, max(10, width))

    def _draw_text(self, painter: QPainter, rect: QRect, text: str, font: QFont, color: QColor) -> None:
        painter.setFont(font)
        shadow_cfg = self._config.font.shadow
        if shadow_cfg.enabled:
            painter.setPen(self._shadow_color)
            painter.drawText(
                rect.translated(int(shadow_cfg.offset_x), int(shadow_cfg.offset_y)),
                Qt.AlignLeft | Qt.AlignVCenter,
                text,
            )
        painter.setPen(color)
        painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, text)
