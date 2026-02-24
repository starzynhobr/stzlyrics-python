from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, Signal

try:
    from winsdk.windows.media.control import (  # type: ignore
        GlobalSystemMediaTransportControlsSessionManager as GSMTCSessionManager,
    )

    WINSKD_AVAILABLE = True
except Exception:  # pragma: no cover - depends on Windows/winsdk install
    GSMTCSessionManager = None  # type: ignore[assignment]
    WINSKD_AVAILABLE = False


logger = logging.getLogger("stzlyrics_overlay.media")
DEBUG_SAMPLE_SECONDS = 0.5


def _timespan_to_seconds(value: Any) -> float:
    if value is None:
        return 0.0
    if hasattr(value, "total_seconds"):
        try:
            return float(value.total_seconds())
        except Exception:
            pass
    if hasattr(value, "duration"):
        try:
            return float(value.duration) / 10_000_000.0
        except Exception:
            pass
    if isinstance(value, (int, float)):
        if abs(float(value)) > 100_000:
            return float(value) / 10_000_000.0
        return float(value)
    return 0.0


def _enum_name(value: Any) -> str:
    if value is None:
        return "Unknown"
    name = getattr(value, "name", None)
    if isinstance(name, str) and name:
        return name
    text = str(value)
    if "." in text:
        return text.rsplit(".", 1)[-1]
    return text


def _normalize_track_part(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


@dataclass(slots=True)
class MediaState:
    artist: str = ""
    title: str = ""
    position_seconds: float = 0.0
    duration_seconds: float = 0.0
    playback_status: str = "Unknown"
    source_app: str = ""
    is_active: bool = False
    polled_at: float = 0.0

    @property
    def is_playing(self) -> bool:
        return self.playback_status.lower() == "playing"

    @property
    def track_key(self) -> str:
        artist = _normalize_track_part(self.artist)
        title = _normalize_track_part(self.title)
        base = f"{artist}|{title}"
        if self.duration_seconds > 1:
            duration_bucket = int(round(self.duration_seconds))
            return f"{base}|{duration_bucket}"
        return base

    @property
    def display_track(self) -> str:
        artist = self.artist.strip()
        title = self.title.strip()
        if artist and title:
            return f"{artist} - {title}"
        return title or artist

    @classmethod
    def empty(cls) -> "MediaState":
        return cls(is_active=False, polled_at=time.time())


class MediaSessionService(QObject):
    state_changed = Signal(object)  # MediaState
    error = Signal(str)

    def __init__(self, poll_interval_ms: int = 300, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._poll_interval_ms = max(150, int(poll_interval_ms))
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_debug_poll_log_at = 0.0
        self._last_poll_started_mono = 0.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._thread_main, name="GSMTCWorker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None

    def set_poll_interval_ms(self, poll_interval_ms: int) -> None:
        self._poll_interval_ms = max(150, int(poll_interval_ms))

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._async_loop())
        except Exception as exc:  # pragma: no cover - runtime-specific
            self.error.emit(f"GSMTC worker falhou: {exc}")

    async def _async_loop(self) -> None:
        if not WINSKD_AVAILABLE:
            self.error.emit("winsdk não está instalado. Execute: pip install winsdk")
            self.state_changed.emit(MediaState.empty())
            return

        try:
            manager = await GSMTCSessionManager.request_async()
        except Exception as exc:  # pragma: no cover - depends on Windows runtime
            self.error.emit(f"Falha ao inicializar GSMTC: {exc}")
            self.state_changed.emit(MediaState.empty())
            return

        while not self._stop_event.is_set():
            try:
                poll_started = time.monotonic()
                gap_ms = 0.0
                if self._last_poll_started_mono > 0.0:
                    gap_ms = max(0.0, (poll_started - self._last_poll_started_mono) * 1000.0)
                self._last_poll_started_mono = poll_started
                state = await self._poll_once(manager)
                poll_elapsed_ms = max(0.0, (time.monotonic() - poll_started) * 1000.0)
                self._emit_poll_debug_log(state, poll_elapsed_ms=poll_elapsed_ms, poll_gap_ms=gap_ms)
                self.state_changed.emit(state)
            except Exception as exc:  # pragma: no cover - runtime-specific
                self.error.emit(f"Erro no polling GSMTC: {exc}")
                self.state_changed.emit(MediaState.empty())
            await asyncio.sleep(self._poll_interval_ms / 1000.0)

    async def _poll_once(self, manager: Any) -> MediaState:
        session = self._pick_session(manager)
        if session is None:
            return MediaState.empty()

        playback_info = self._safe_call(session, "get_playback_info")
        playback_status = _enum_name(getattr(playback_info, "playback_status", None))

        timeline = self._safe_call(session, "get_timeline_properties")
        position_seconds = _timespan_to_seconds(getattr(timeline, "position", None))
        duration_seconds = _timespan_to_seconds(getattr(timeline, "end_time", None))

        try:
            media_props = await session.try_get_media_properties_async()
        except Exception:
            media_props = None

        artist = str(getattr(media_props, "artist", "") or "").strip()
        title = str(getattr(media_props, "title", "") or "").strip()
        source_app = str(getattr(session, "source_app_user_model_id", "") or "")
        return MediaState(
            artist=artist,
            title=title,
            position_seconds=max(0.0, position_seconds),
            duration_seconds=max(0.0, duration_seconds),
            playback_status=playback_status,
            source_app=source_app,
            is_active=bool(artist or title),
            polled_at=time.time(),
        )

    def _emit_poll_debug_log(self, state: MediaState, *, poll_elapsed_ms: float = 0.0, poll_gap_ms: float = 0.0) -> None:
        now = time.monotonic()
        if (now - self._last_debug_poll_log_at) < DEBUG_SAMPLE_SECONDS:
            return
        self._last_debug_poll_log_at = now
        logger.debug(
            "player_poll pos=%.3f dur=%.3f playing=%s state=%s source=%r active=%s poll_ms=%.1f gap_ms=%.1f",
            state.position_seconds,
            state.duration_seconds,
            state.is_playing,
            state.playback_status,
            state.source_app,
            state.is_active,
            poll_elapsed_ms,
            poll_gap_ms,
        )

    def _safe_call(self, obj: Any, method_name: str) -> Any:
        method = getattr(obj, method_name, None)
        if callable(method):
            return method()
        return None

    def _pick_session(self, manager: Any) -> Any:
        current = None
        try:
            current = manager.get_current_session()
        except Exception:
            current = None

        sessions: list[Any] = []
        try:
            raw_sessions = manager.get_sessions()
            sessions = list(raw_sessions) if raw_sessions is not None else []
        except Exception:
            sessions = []

        if not sessions and current is not None:
            return current
        if not sessions:
            return None

        def score(session: Any) -> tuple[int, int]:
            source = str(getattr(session, "source_app_user_model_id", "") or "").lower()
            playback_info = self._safe_call(session, "get_playback_info")
            status_name = _enum_name(getattr(playback_info, "playback_status", None)).lower()
            pts = 0
            if "spotify" in source:
                pts += 20
            if status_name == "playing":
                pts += 10
            if current is not None and session == current:
                pts += 5
            return pts, len(source)

        sessions.sort(key=score, reverse=True)
        return sessions[0]
