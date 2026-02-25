from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QMouseEvent, QPainter
from PySide6.QtWidgets import QWidget

from app.config import AppConfig
from app.layout_presets import build_layout_render_model, normalize_context_animation_style
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
        if config.get_preset_always_on_top(getattr(config.overlay, "layout_preset", "")):
            flags |= Qt.WindowStaysOnTopHint
        super().__init__(parent, flags)

        self._config = config
        self._track_text = "Aguardando mídia..."
        self._lyric_text = "Conectando ao GSMTC..."
        self._status_hint = ""
        self._clock_debug_text = ""
        self._track_base_text = "Aguardando mídia..."
        self._context_lines: list[str] | None = None
        self._context_current_slot = 0
        self._context_anchor_index = -1
        self._context_prev_lines: list[str] | None = None
        self._context_prev_slot = 0
        self._context_anim_started_at = 0.0
        self._context_anim_direction = 0
        self._context_anim_style = "slide_fade"
        self._click_through = bool(config.overlay.click_through)
        self._snap_enabled = bool(config.overlay.snap_to_taskbar)
        self._dragging = False
        self._drag_offset = QPoint()
        self._track_color = QColor(200, 200, 200, 255)
        self._lyric_color = QColor(255, 255, 255, 255)
        self._shadow_color = QColor(0, 0, 0, 255)
        self._layout_model = build_layout_render_model("detailed")
        self._debug_clock_overlay_enabled = False
        self._always_on_top_enabled = bool(
            config.get_preset_always_on_top(getattr(config.overlay, "layout_preset", ""))
        )
        self._topmost_guard_timer = QTimer(self)
        self._topmost_guard_timer.setInterval(250)
        self._topmost_guard_timer.timeout.connect(self._topmost_guard_tick)
        self._context_anim_timer = QTimer(self)
        self._context_anim_timer.setInterval(16)
        self._context_anim_timer.timeout.connect(self._context_anim_tick)

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.apply_config(config)

    def apply_config(self, config: AppConfig) -> None:
        self._config = config
        self._click_through = bool(config.overlay.click_through)
        self._snap_enabled = bool(config.overlay.snap_to_taskbar)
        self._always_on_top_enabled = bool(
            config.get_preset_always_on_top(getattr(config.overlay, "layout_preset", ""))
        )
        self._context_anim_style = normalize_context_animation_style(
            getattr(config.overlay, "context_animation_style", "slide_fade")
        )
        self._apply_qt_topmost_flag()
        self.apply_layout_preset(getattr(self._config.overlay, "layout_preset", "detailed"))
        self._debug_clock_overlay_enabled = bool(getattr(self._config.clock, "debug_clock_overlay", False))
        self._track_color = _safe_color(self._config.font.track_color, "#C8C8C8FF")
        self._lyric_color = _safe_color(
            self._config.get_preset_font_color(getattr(self._config.overlay, "layout_preset", "")),
            "#FFFFFFFF",
        )
        self._shadow_color = _safe_color(self._config.font.shadow.color, "#000000FF")
        self._log_color_application()
        self._apply_overlay_size()
        self.update()
        self.apply_click_through()
        self._apply_native_topmost_state()
        self._sync_topmost_guard_timer()

    def _apply_qt_topmost_flag(self) -> None:
        desired = bool(self._always_on_top_enabled)
        current = bool(self.windowFlags() & Qt.WindowStaysOnTopHint)
        if current == desired:
            return
        was_visible = self.isVisible()
        pos = self.pos()
        size = self.size()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, desired)
        if was_visible:
            self.show()
            self.resize(size)
            self.move(pos)

    def apply_layout_preset(self, preset: str) -> None:
        self._layout_model = build_layout_render_model(preset)
        logger.info("Applying layout preset preset=%s", self._layout_model.preset.value)
        self._apply_overlay_size()
        if not self.lyric_context_request():
            self._clear_lyric_context()
        self.update()

    def _apply_overlay_size(self) -> None:
        width = int(getattr(self._config.overlay, "width", self.width() or 0))
        base_height = int(getattr(self._config.overlay, "height", self.height() or 0))
        min_height = self._minimum_height_for_current_layout()
        height = max(base_height, min_height)
        self.resize(max(1, width), max(1, height))

    def _minimum_height_for_current_layout(self) -> int:
        before = max(0, int(getattr(self._layout_model, "context_before", 0) or 0))
        after = max(0, int(getattr(self._layout_model, "context_after", 0) or 0))
        if before <= 0 and after <= 0:
            return 0
        total_lines = before + 1 + after
        lyric_font = QFont(self._config.font.family, int(self._config.font.size))
        lyric_line_height = max(1, QFontMetrics(lyric_font).height())
        line_gap = max(0, int(getattr(self._layout_model, "context_line_gap", 4) or 0))
        content_height = (lyric_line_height * total_lines) + (line_gap * max(0, total_lines - 1))
        pad_y = int(getattr(self._config.overlay, "padding_y", 0))
        header_height = int(self._layout_model.header_height) if self._layout_model.show_header else 0
        header_gap = int(self._layout_model.header_gap) if self._layout_model.show_header else 0
        return (pad_y * 2) + header_height + header_gap + content_height + 2

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
        self._clear_lyric_context()
        self._lyric_text = (text or "").strip()
        self.update()

    def lyric_context_request(self) -> tuple[int, int] | None:
        before = int(getattr(self._layout_model, "context_before", 0) or 0)
        after = int(getattr(self._layout_model, "context_after", 0) or 0)
        if before <= 0 and after <= 0:
            return None
        return max(0, before), max(0, after)

    def has_lyric_context(self) -> bool:
        return self._context_lines is not None

    def set_lyric_context(self, lines: list[str], current_slot: int, anchor_index: int) -> None:
        request = self.lyric_context_request()
        if request is None:
            current_text = ""
            if lines and 0 <= int(current_slot) < len(lines):
                current_text = lines[int(current_slot)] or ""
            self.set_lyric_text(current_text)
            return
        sanitized = [str(line or "") for line in (lines or [])]
        if not sanitized:
            self.set_lyric_text("")
            return
        slot = int(current_slot)
        if slot < 0:
            slot = 0
        if slot >= len(sanitized):
            slot = len(sanitized) - 1
        prev_lines = self._context_lines
        prev_anchor = self._context_anchor_index
        prev_slot = self._context_current_slot
        self._context_lines = sanitized
        self._context_current_slot = slot
        self._context_anchor_index = int(anchor_index)
        self._lyric_text = sanitized[slot] or ""

        animate = (
            bool(getattr(self._layout_model, "animate_context_transition", False))
            and self._context_anim_style != "none"
        )
        duration_ms = int(getattr(self._layout_model, "context_anim_duration_ms", 220) or 220)
        delta_idx = self._context_anchor_index - prev_anchor
        if (
            animate
            and prev_lines is not None
            and prev_anchor >= 0
            and duration_ms > 0
            and delta_idx in (-1, 1)
            and len(prev_lines) == len(sanitized)
        ):
            self._context_prev_lines = list(prev_lines)
            self._context_prev_slot = int(prev_slot)
            self._context_anim_direction = int(delta_idx)
            self._context_anim_started_at = time.monotonic()
            if self.isVisible() and (not self._context_anim_timer.isActive()):
                self._context_anim_timer.start()
        else:
            self._clear_context_animation()
        self.update()

    def set_status_hint(self, text: str) -> None:
        self._status_hint = (text or "").strip()
        self._rebuild_track_text()
        self.update()

    def set_clock_debug_text(self, text: str) -> None:
        self._clock_debug_text = (text or "").strip()
        self._rebuild_track_text()
        self.update()

    def _clear_context_animation(self) -> None:
        self._context_prev_lines = None
        self._context_prev_slot = 0
        self._context_anim_started_at = 0.0
        self._context_anim_direction = 0
        if self._context_anim_timer.isActive():
            self._context_anim_timer.stop()

    def _clear_lyric_context(self) -> None:
        self._clear_context_animation()
        self._context_lines = None
        self._context_current_slot = 0
        self._context_anchor_index = -1

    def _context_anim_tick(self) -> None:
        if self._context_prev_lines is None or self._context_anim_direction == 0:
            self._clear_context_animation()
            return
        progress = self._context_anim_progress()
        if progress >= 1.0:
            self._clear_context_animation()
        self.update()

    def _context_anim_progress(self) -> float:
        if self._context_prev_lines is None or self._context_anim_direction == 0:
            return 1.0
        duration_ms = max(1, int(getattr(self._layout_model, "context_anim_duration_ms", 220) or 220))
        elapsed_ms = (time.monotonic() - self._context_anim_started_at) * 1000.0
        if elapsed_ms <= 0.0:
            return 0.0
        if elapsed_ms >= duration_ms:
            return 1.0
        return max(0.0, min(1.0, elapsed_ms / float(duration_ms)))

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

    def _apply_native_topmost_state(self) -> None:
        try:
            hwnd = int(self.winId())
        except Exception:
            hwnd = 0
        if self._always_on_top_enabled:
            self._ensure_topmost_if_needed()
            return
        set_window_topmost(hwnd, False, force_reorder=False)

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
            layout_preset=getattr(self._config.overlay, "layout_preset", ""),
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
        if self._context_anim_timer.isActive():
            self._context_anim_timer.stop()

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
        if self._context_lines is not None and self.lyric_context_request() is not None:
            self._draw_context_lyrics(painter, lyric_rect, lyric_font)
        else:
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

    def _draw_context_lyrics(self, painter: QPainter, rect: QRect, font: QFont) -> None:
        lines = self._context_lines or []
        if not lines:
            self._draw_text(
                painter,
                rect=rect,
                text=self._elide(font, self._lyric_text, rect.width()),
                font=font,
                color=self._lyric_color,
            )
            return
        painter.save()
        painter.setClipRect(rect)
        progress = self._context_anim_progress()
        fm = QFontMetrics(font)
        line_height = max(1, fm.height())
        pitch = line_height + max(0, int(getattr(self._layout_model, "context_line_gap", 4) or 0))
        if self._context_prev_lines is not None and self._context_anim_direction in (-1, 1) and progress < 1.0:
            anim_style = normalize_context_animation_style(self._context_anim_style)
            use_slide = anim_style in ("slide", "slide_fade")
            use_fade = anim_style in ("fade", "slide_fade")
            visual_sign = -1 if self._context_anim_direction > 0 else 1
            step = float(pitch)
            old_offset = (visual_sign * progress * step) if use_slide else 0.0
            new_offset = ((-visual_sign) * (1.0 - progress) * step) if use_slide else 0.0
            old_opacity = max(0.0, 1.0 - progress) if use_fade else 1.0
            new_opacity = min(1.0, 0.25 + (0.75 * progress)) if use_fade else 1.0
            self._draw_context_block(
                painter,
                rect=rect,
                font=font,
                lines=self._context_prev_lines,
                current_slot=self._context_prev_slot,
                y_offset=old_offset,
                block_opacity=old_opacity,
            )
            self._draw_context_block(
                painter,
                rect=rect,
                font=font,
                lines=lines,
                current_slot=self._context_current_slot,
                y_offset=new_offset,
                block_opacity=new_opacity,
            )
        else:
            self._draw_context_block(
                painter,
                rect=rect,
                font=font,
                lines=lines,
                current_slot=self._context_current_slot,
                y_offset=0.0,
                block_opacity=1.0,
            )
        painter.restore()

    def _draw_context_block(
        self,
        painter: QPainter,
        *,
        rect: QRect,
        font: QFont,
        lines: list[str],
        current_slot: int,
        y_offset: float,
        block_opacity: float,
    ) -> None:
        if not lines or rect.height() <= 0 or rect.width() <= 0 or block_opacity <= 0.0:
            return
        fm = QFontMetrics(font)
        line_height = max(1, fm.height())
        gap = max(0, int(getattr(self._layout_model, "context_line_gap", 4) or 0))
        pitch = line_height + gap
        center_y = rect.center().y()
        for slot, raw_text in enumerate(lines):
            text = str(raw_text or "")
            if not text:
                continue
            rel = slot - int(current_slot)
            line_center_y = center_y + int(round(y_offset)) + (rel * pitch)
            line_rect = QRect(rect.left(), int(line_center_y - (line_height // 2)), rect.width(), line_height)
            if line_rect.bottom() < rect.top() or line_rect.top() > rect.bottom():
                continue
            distance = abs(rel)
            alpha_scale = 1.0 if distance == 0 else (0.55 if distance == 1 else 0.28)
            color = QColor(self._lyric_color)
            color.setAlpha(max(0, min(255, int(round(color.alpha() * alpha_scale)))))
            painter.save()
            painter.setOpacity(max(0.0, min(1.0, block_opacity)))
            self._draw_text(
                painter,
                rect=line_rect,
                text=self._elide(font, text, line_rect.width()),
                font=font,
                color=color,
            )
            painter.restore()
