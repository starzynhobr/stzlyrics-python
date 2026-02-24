from __future__ import annotations

import concurrent.futures
import logging
import os
import re
import sys
import threading
import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from app.config import AppConfig, AppPaths, load_config, save_config
from app.services.cache import LyricsCache, build_track_cache_key
from app.services.lrclib_client import LrclibClient, LrclibResult
from app.services.lrclib_client import (
    OUTCOME_FAIL_TRANSIENT_NETWORK,
    OUTCOME_SUCCESS_NO_SYNCED,
)
from app.services.lyrics_sync import LyricsSynchronizer, parse_lrc
from app.services.media_session import MediaSessionService, MediaState
from app.ui.overlay_window import OverlayWindow, PositionPayload
from app.ui.settings_window import SettingsValues, SettingsWindow
from app.ui.system_tray import TrayController

if "--debug" in sys.argv:
    print(f"[IMPORT_AUDIT] controller.__file__={__file__}", file=sys.stderr)
    print(f"[IMPORT_AUDIT] controller.abspath={os.path.abspath(__file__)}", file=sys.stderr)


TRACK_CHANGE_DEBOUNCE_MS = 350
FAILURE_HOLD_MS = 2500
GOOD_LINE_FRESH_SECONDS = 6.0
DEFAULT_NO_SYNCED_TEXT = "Sem letra sincronizada para esta música."
TRANSIENT_RETRY_DELAY_MS = 5000
TIMESTAMP_IN_TEXT_RE = re.compile(r"\[(\d{1,2}:\d{2}(?:\.\d{1,3})?)\]")
CLOCK_DEBUG_SAMPLE_SECONDS = 0.5
CLOCK_BACKWARD_LAG_IGNORE_SECONDS = 0.30
CLOCK_PLAYING_PROGRESS_GRACE_SECONDS = 1.2
CLOCK_PLAY_STATE_HYSTERESIS_POLLS = 2
# Ignore tiny raw jitter from GSMTC (especially while paused).
CLOCK_RAW_PROGRESS_EPSILON_SECONDS = 0.20


@dataclass(slots=True)
class _LyricsRequest:
    request_id: int
    track_seq: int
    track_key: str
    artist: str
    title: str
    cancel_event: threading.Event
    started_at: float


@dataclass(slots=True)
class _QueuedFetch:
    track_seq: int
    track_key: str
    artist: str
    title: str
    force_network: bool = False


@dataclass(slots=True)
class _PendingTrackCandidate:
    track_seq: int
    track_key: str
    artist: str
    title: str


@dataclass(slots=True)
class _ClockUpdateResult:
    raw_pos: float
    est_before: float
    est_after: float
    err: float
    reset_reason: str = ""
    raw_ignored: bool = False


class _PlaybackClock:
    def __init__(self) -> None:
        self.track_key: str = ""
        self.anchor_pos: float = 0.0
        self.anchor_time: float = 0.0
        self.duration: float = 0.0
        self.is_playing: bool = False  # effective_playing (kept name for compatibility)
        self.initialized: bool = False
        self.last_raw_pos: float = 0.0
        self.last_error: float = 0.0
        self.last_est_pos: float = 0.0
        self._last_est_pos_valid: bool = False
        self._last_raw_advance_mono: float = 0.0
        self._candidate_playing: bool | None = None
        self._candidate_playing_count: int = 0
        self._last_est_clamped: bool = False
        self._last_est_clamp_from: float = 0.0
        self._last_est_clamp_to: float = 0.0
        self.seek_threshold_s: float = 1.2
        self.backward_lag_ignore_s: float = CLOCK_BACKWARD_LAG_IGNORE_SECONDS
        self.enable_soft_correction: bool = False
        self.soft_correction_gain: float = 0.15
        self.soft_correction_clamp_s: float = 0.8

    def configure(
        self,
        *,
        seek_threshold_s: float,
        enable_soft_correction: bool,
        soft_correction_gain: float,
        soft_correction_clamp_s: float,
        backward_lag_ignore_s: float = CLOCK_BACKWARD_LAG_IGNORE_SECONDS,
    ) -> None:
        self.seek_threshold_s = max(0.25, float(seek_threshold_s))
        self.backward_lag_ignore_s = max(0.05, float(backward_lag_ignore_s))
        self.enable_soft_correction = bool(enable_soft_correction)
        self.soft_correction_gain = max(0.0, min(1.0, float(soft_correction_gain)))
        self.soft_correction_clamp_s = max(0.0, float(soft_correction_clamp_s))

    def reset_inactive(self) -> None:
        self.track_key = ""
        self.anchor_pos = 0.0
        self.anchor_time = 0.0
        self.duration = 0.0
        self.is_playing = False
        self.initialized = False
        self.last_raw_pos = 0.0
        self.last_error = 0.0
        self.last_est_pos = 0.0
        self._last_est_pos_valid = False
        self._last_raw_advance_mono = 0.0
        self._candidate_playing = None
        self._candidate_playing_count = 0
        self._last_est_clamped = False
        self._last_est_clamp_from = 0.0
        self._last_est_clamp_to = 0.0

    def estimated_position(self, now_mono: float | None = None) -> float:
        if not self.initialized:
            return 0.0
        now = time.monotonic() if now_mono is None else now_mono
        if self.is_playing:
            pos = self.anchor_pos + max(0.0, now - self.anchor_time)
        else:
            pos = self.anchor_pos
        pos = self._clamp_position(pos)
        self._last_est_clamped = False
        if self.is_playing and self._last_est_pos_valid and pos < self.last_est_pos:
            self._last_est_clamped = True
            self._last_est_clamp_from = pos
            self._last_est_clamp_to = self.last_est_pos
            pos = self.last_est_pos
        self.last_est_pos = pos
        self._last_est_pos_valid = True
        return pos

    def apply_state(self, state: MediaState, now_mono: float | None = None) -> _ClockUpdateResult:
        now = time.monotonic() if now_mono is None else now_mono
        raw_pos = max(0.0, float(state.position_seconds or 0.0))
        self.duration = max(0.0, float(state.duration_seconds or 0.0))
        raw_status = str(getattr(state, "playback_status", "") or "").lower()
        prev_effective_playing = self.is_playing
        prev_raw_pos = self.last_raw_pos

        if (not self.initialized) or (state.track_key != self.track_key):
            self.track_key = state.track_key
            self.anchor_pos = self._clamp_position(raw_pos)
            self.anchor_time = now
            self.is_playing = bool(state.is_playing)
            self.initialized = True
            self.last_raw_pos = raw_pos
            self.last_error = 0.0
            self.last_est_pos = self.anchor_pos
            self._last_est_pos_valid = True
            self._candidate_playing = self.is_playing
            self._candidate_playing_count = 0
            # Do not seed "recent progress" while paused; that causes false PLAYING flicker on startup.
            self._last_raw_advance_mono = now if self.is_playing else 0.0
            return _ClockUpdateResult(
                raw_pos=raw_pos,
                est_before=raw_pos,
                est_after=self.anchor_pos,
                err=0.0,
                reset_reason="track_change" if state.track_key else "init",
            )

        if raw_pos > (prev_raw_pos + CLOCK_RAW_PROGRESS_EPSILON_SECONDS):
            self._last_raw_advance_mono = now

        est_before = self.estimated_position(now)
        err = raw_pos - est_before
        raw_delta = raw_pos - prev_raw_pos
        self.last_raw_pos = raw_pos
        self.last_error = err

        candidate_playing = self._compute_candidate_playing(
            raw_is_playing=bool(state.is_playing),
            raw_status=raw_status,
            now_mono=now,
        )
        explicit_paused = (not bool(state.is_playing)) and (raw_status == "paused")
        if explicit_paused:
            # Trust an explicit PAUSED signal immediately to avoid multi-second lag
            # from the recent-progress grace window + hysteresis.
            self._candidate_playing = False
            self._candidate_playing_count = CLOCK_PLAY_STATE_HYSTERESIS_POLLS
            self.is_playing = False
        else:
            self._apply_play_state_hysteresis(candidate_playing)

        if self.is_playing and (err < -self.backward_lag_ignore_s):
            # GSMTC (notably Spotify) can freeze the reported timeline position for
            # several polls and then jump forward. Ignore that stale raw position
            # while playing unless there was a clear backward jump (seek).
            raw_backward_seek = raw_delta < -self.seek_threshold_s
            if not raw_backward_seek:
                return _ClockUpdateResult(
                    raw_pos=raw_pos,
                    est_before=est_before,
                    est_after=est_before,
                    err=err,
                    reset_reason="raw_ignored_backward_lag",
                    raw_ignored=True,
                )

        if abs(err) > self.seek_threshold_s:
            self.anchor_pos = self._clamp_position(raw_pos)
            self.anchor_time = now
            self.is_playing = bool(self.is_playing)
            self.last_error = 0.0
            self.last_est_pos = self.anchor_pos
            self._last_est_pos_valid = True
            return _ClockUpdateResult(
                raw_pos=raw_pos,
                est_before=est_before,
                est_after=self.anchor_pos,
                err=err,
                reset_reason="seek_reanchor",
            )

        if (not prev_effective_playing) and self.is_playing:
            # Resume/start clock from the greater of raw and current estimate to avoid backward pulls.
            self.anchor_pos = self._clamp_position(max(raw_pos, est_before))
            self.anchor_time = now
            self.last_error = 0.0
            self.last_est_pos = self.anchor_pos
            self._last_est_pos_valid = True
            return _ClockUpdateResult(
                raw_pos=raw_pos,
                est_before=est_before,
                est_after=self.anchor_pos,
                err=err,
                reset_reason="resume_anchor",
            )

        if prev_effective_playing and (not self.is_playing):
            # Freeze at current estimate (not raw) so delayed raw doesn't pull the clock backward.
            self.anchor_pos = self._clamp_position(max(est_before, raw_pos))
            self.anchor_time = now
            self.last_error = raw_pos - self.anchor_pos
            self.last_est_pos = self.anchor_pos
            self._last_est_pos_valid = True
            return _ClockUpdateResult(
                raw_pos=raw_pos,
                est_before=est_before,
                est_after=self.anchor_pos,
                err=err,
                reset_reason="pause_anchor",
            )

        if self.enable_soft_correction and abs(err) > 0.0:
            correction = max(
                -self.soft_correction_clamp_s,
                min(self.soft_correction_clamp_s, err * self.soft_correction_gain),
            )
            if correction:
                self.anchor_pos = self._clamp_position(self.anchor_pos + correction)
                self.last_error = raw_pos - self.estimated_position(now)

        # Do not force effective_playing here. It must remain controlled by
        # hysteresis/candidate state (and explicit reset branches), otherwise a
        # paused raw state can be turned back into PLAYING and cause reanchor loops.
        return _ClockUpdateResult(
            raw_pos=raw_pos,
            est_before=est_before,
            est_after=self.estimated_position(now),
            err=err,
            reset_reason="",
        )

    def _compute_candidate_playing(self, raw_is_playing: bool, raw_status: str, now_mono: float) -> bool:
        if raw_is_playing or raw_status == "playing":
            return True
        if raw_status == "paused":
            return False
        recent_progress = (now_mono - self._last_raw_advance_mono) <= CLOCK_PLAYING_PROGRESS_GRACE_SECONDS
        return bool(recent_progress)

    def _apply_play_state_hysteresis(self, candidate_playing: bool) -> None:
        if self._candidate_playing is None or self._candidate_playing != candidate_playing:
            self._candidate_playing = candidate_playing
            self._candidate_playing_count = 1
        else:
            self._candidate_playing_count += 1
        if self._candidate_playing_count >= CLOCK_PLAY_STATE_HYSTERESIS_POLLS:
            self.is_playing = bool(candidate_playing)

    def _clamp_position(self, pos: float) -> float:
        if self.duration > 0.0:
            return max(0.0, min(float(pos), self.duration))
        return max(0.0, float(pos))


class AppController(QObject):
    _lyrics_result_ready = Signal(object)
    _fetch_progress_ready = Signal(object)

    def __init__(
        self,
        config: AppConfig,
        paths: AppPaths,
        logger: logging.Logger,
        overlay: OverlayWindow,
        tray: TrayController,
        media_service: MediaSessionService,
        lyrics_cache: LyricsCache,
        lrclib_client: LrclibClient,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.paths = paths
        self.logger = logger
        self.overlay = overlay
        self.tray = tray
        self.media_service = media_service
        self.lyrics_cache = lyrics_cache
        self.lrclib_client = lrclib_client

        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="lyrics")
        self.sync = LyricsSynchronizer()
        self._playback_clock = _PlaybackClock()

        self._current_media = MediaState.empty()
        self._current_track_key = ""
        self._current_track_seq = 0
        self._last_lyric_line = ""
        self._last_good_lyric_line = ""
        self._last_good_lyric_at = 0.0
        self._latched_paused_line: str | None = None
        self._latched_paused_position: float | None = None
        self._was_effective_playing: bool = False
        self._overlay_visible = True

        self._request_counter = 0
        self._active_request: _LyricsRequest | None = None
        self._fetch_inflight = False
        self._queued_fetch: _QueuedFetch | None = None
        self._pending_track_candidate: _PendingTrackCandidate | None = None
        self._settings_window: SettingsWindow | None = None

        self._pending_fallback_track_seq = -1
        self._pending_fallback_text = ""
        self._transient_retry_target: _QueuedFetch | None = None
        self._last_header_debug_log_at = 0.0
        self._last_clock_debug_log_at = 0.0
        self._last_clock_debug_raw_pos: float | None = None
        self._started = False

        self._track_debounce_timer = QTimer(self)
        self._track_debounce_timer.setSingleShot(True)
        self._track_debounce_timer.timeout.connect(self._flush_debounced_track_change)

        self._failure_hold_timer = QTimer(self)
        self._failure_hold_timer.setSingleShot(True)
        self._failure_hold_timer.timeout.connect(self._apply_pending_fallback)

        self._transient_retry_timer = QTimer(self)
        self._transient_retry_timer.setSingleShot(True)
        self._transient_retry_timer.timeout.connect(self._run_transient_retry)

        self._ui_clock_timer = QTimer(self)
        self._ui_clock_timer.timeout.connect(self._on_ui_clock_tick)

        self._lyrics_result_ready.connect(self._on_lyrics_result)
        self._fetch_progress_ready.connect(self._on_fetch_progress)

        self.overlay.position_committed.connect(self._on_position_committed)
        self.media_service.state_changed.connect(self._on_media_state)
        self.media_service.error.connect(self._on_media_error)

        self.tray.open_settings_requested.connect(self._open_settings_window)
        self.tray.open_cache_requested.connect(self._open_cache_folder)
        self.tray.reload_config_requested.connect(self._reload_config_from_disk)
        self.tray.toggle_visible_requested.connect(self._toggle_overlay_visibility)
        app = QApplication.instance()
        if app is not None:
            self.tray.quit_requested.connect(app.quit)

        self._apply_clock_config()

    def start(self) -> None:
        self._started = True
        self.overlay.restore_position()
        self.overlay.show()
        self.tray.show()
        self.tray.set_tooltip("STZLyrics Overlay")
        self.overlay.set_status_hint("")
        self.overlay.set_clock_debug_text("")
        self.overlay.set_lyric_text("Aguardando música...")
        self._ui_clock_timer.start()
        self.media_service.start()

    def _total_attempts(self) -> int:
        return max(1, int(self.config.network.lrclib_max_retries) + 1)

    def shutdown(self) -> None:
        self._started = False
        self._ui_clock_timer.stop()
        self._transient_retry_timer.stop()
        self._cancel_active_fetch()
        self.media_service.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)
        if self._settings_window is not None:
            self._settings_window.close()
        self.tray.hide()

    def _on_media_error(self, message: str) -> None:
        self.logger.warning(message)
        if "winsdk" in message.lower():
            self.overlay.set_status_hint("")
            self.overlay.set_lyric_text("winsdk não instalado")
        self.tray.set_tooltip(f"STZLyrics Overlay - {message}")

    def _on_media_state(self, state_obj: object) -> None:
        if not isinstance(state_obj, MediaState):
            return

        state = state_obj
        self._current_media = state
        clock_update = self._playback_clock.apply_state(state)
        if clock_update.reset_reason == "seek_reanchor":
            self._clear_paused_lyric_latch("seek_reanchor")
            self._clear_paused_position_latch("seek_reanchor")
            self.logger.debug(
                "clock_seek_reanchor raw_pos=%.3f est_before=%.3f err=%.3f seek_threshold=%.3f raw_status=%r effective_playing=%s track_key=%r",
                clock_update.raw_pos,
                clock_update.est_before,
                clock_update.err,
                self._playback_clock.seek_threshold_s,
                state.playback_status,
                self._playback_clock.is_playing,
                state.track_key,
            )
        elif clock_update.reset_reason == "resume_anchor":
            self._clear_paused_lyric_latch("resume_anchor")
            self._clear_paused_position_latch("resume_anchor")
        elif clock_update.reset_reason == "raw_ignored_backward_lag":
            self.logger.debug(
                "raw_ignored_backward_lag raw_pos=%.3f est_before=%.3f err=%.3f track_key=%r",
                clock_update.raw_pos,
                clock_update.est_before,
                clock_update.err,
                state.track_key,
            )
        self._log_clock_update_debug(state, clock_update)
        self._refresh_ui_from_media_state(force=True, source="media_state")
        self.tray.set_tooltip(state.display_track or "STZLyrics Overlay")

        if not state.is_active:
            self.logger.debug("Media inactive: clearing track state")
            self._playback_clock.reset_inactive()
            self._track_debounce_timer.stop()
            self._transient_retry_timer.stop()
            self._transient_retry_target = None
            self._pending_track_candidate = None
            self._queued_fetch = None
            self._cancel_active_fetch()
            self.overlay.set_status_hint("")
            self.overlay.set_clock_debug_text("")
            if self._current_track_key:
                self._current_track_key = ""
                self.sync.clear()
                self._clear_paused_lyric_latch("media_inactive")
                self._clear_paused_position_latch("media_inactive")
                self._last_lyric_line = ""
                self.overlay.set_lyric_text("Nenhuma mídia ativa")
            return

        # Ignore transients while metadata is incomplete; GSMTC commonly flickers during track changes.
        if not self._is_fetchable_track(state):
            self.overlay.set_status_hint("Aguardando metadados...")
            return

        if state.track_key != self._current_track_key:
            self.logger.info("Track change detected old=%r new=%r", self._current_track_key, state.track_key)
            self._register_track_change(state)
            return

    def _is_fetchable_track(self, state: MediaState) -> bool:
        artist = (state.artist or "").strip()
        title = (state.title or "").strip()
        if not artist or not title:
            return False
        lowered = {artist.lower(), title.lower()}
        if "n/a" in lowered:
            return False
        return True

    def _log_header_update_debug(self, state: MediaState, pos_for_header: float, source: str) -> None:
        now = time.monotonic()
        if (now - self._last_header_debug_log_at) < 0.5:
            return
        self._last_header_debug_log_at = now

        def fmt(seconds: float) -> str:
            total = max(0, int(seconds))
            minutes, secs = divmod(total, 60)
            hours, minutes = divmod(minutes, 60)
            if hours:
                return f"{hours}:{minutes:02d}:{secs:02d}"
            return f"{minutes}:{secs:02d}"

        self.logger.debug(
            "header_update pos_display=%s total_display=%s source=%s pos_raw=%.3f pos_header=%.3f dur_raw=%.3f playing=%s track_key=%r",
            fmt(pos_for_header),
            fmt(state.duration_seconds) if state.duration_seconds > 0 else "--:--",
            source,
            state.position_seconds,
            pos_for_header,
            state.duration_seconds,
            state.is_playing,
            state.track_key,
        )

    def _log_clock_update_debug(self, state: MediaState, update: _ClockUpdateResult) -> None:
        now = time.monotonic()
        if (now - self._last_clock_debug_log_at) < CLOCK_DEBUG_SAMPLE_SECONDS:
            return
        self._last_clock_debug_log_at = now
        raw_pos = float(state.position_seconds or 0.0)
        prev_raw = self._last_clock_debug_raw_pos
        delta_raw = 0.0 if prev_raw is None else (raw_pos - prev_raw)
        self._last_clock_debug_raw_pos = raw_pos
        self.logger.debug(
            "clock_tick raw_status=%r raw_pos=%.3f last_pos_raw=%s delta_pos_raw=%+.3f est_pos=%.3f last_est_pos=%.3f err=%.3f effective_playing=%s candidate_playing=%s candidate_count=%d track_key=%r reset=%s",
            state.playback_status,
            raw_pos,
            "None" if prev_raw is None else f"{prev_raw:.3f}",
            delta_raw,
            update.est_after,
            self._playback_clock.last_est_pos,
            update.err,
            self._playback_clock.is_playing,
            self._playback_clock._candidate_playing,
            self._playback_clock._candidate_playing_count,
            state.track_key,
            update.reset_reason or "-",
        )

    def _on_ui_clock_tick(self) -> None:
        if not self._current_media.is_active:
            return
        self._refresh_ui_from_media_state(force=False, source="ui_timer")

    def _refresh_ui_from_media_state(self, force: bool = False, *, source: str = "media_state") -> None:
        if not self._current_media.is_active:
            return
        effective_playing = bool(self._playback_clock.is_playing)
        pos_raw = max(0.0, float(self._current_media.position_seconds or 0.0))
        pos_est = self._playback_clock.estimated_position()
        if effective_playing:
            if self._latched_paused_position is not None:
                self._clear_paused_position_latch("playing")
            pos_for_ui = pos_est
        else:
            if self._latched_paused_position is None:
                self._latched_paused_position = max(pos_est, pos_raw)
            pos_for_ui = self._latched_paused_position

        source_short = self._current_media.source_app.split("!")[-1] if self._current_media.source_app else ""
        self.overlay.set_track_state(
            artist=self._current_media.artist,
            title=self._current_media.title,
            position_seconds=pos_for_ui,
            duration_seconds=self._current_media.duration_seconds,
            is_playing=effective_playing,
            source_app=source_short,
        )
        self._update_clock_debug_overlay(pos_for_ui)
        self._log_header_update_debug(self._current_media, pos_for_ui, source=source)
        self._update_synced_lyric_line(force=force, position_seconds=pos_for_ui, effective_playing=effective_playing)

    def _update_clock_debug_overlay(self, pos_est: float) -> None:
        if not bool(getattr(self.config.clock, "debug_clock_overlay", False)):
            self.overlay.set_clock_debug_text("")
            return
        raw = float(self._current_media.position_seconds or 0.0)
        err = raw - pos_est
        self.overlay.set_clock_debug_text(f"clk raw:{raw:.2f} est:{pos_est:.2f} err:{err:+.2f}")

    def _register_track_change(self, state: MediaState) -> None:
        if self._track_debounce_timer.isActive():
            self.logger.debug("Debounce reset for track change new=%r", state.track_key)
        self._clear_paused_lyric_latch("track_change")
        self._clear_paused_position_latch("track_change")
        self._current_track_key = state.track_key
        self._current_track_seq += 1
        self._pending_track_candidate = _PendingTrackCandidate(
            track_seq=self._current_track_seq,
            track_key=state.track_key,
            artist=state.artist,
            title=state.title,
        )
        self._track_debounce_timer.start(TRACK_CHANGE_DEBOUNCE_MS)
        self.logger.info(
            "Debounce start track_seq=%s track_key=%r delay_ms=%s",
            self._current_track_seq,
            self._current_track_key,
            TRACK_CHANGE_DEBOUNCE_MS,
        )
        self._queued_fetch = None
        self._transient_retry_timer.stop()
        self._transient_retry_target = None
        self._cancel_active_fetch()
        self._failure_hold_timer.stop()
        self.overlay.set_status_hint("")

    def _flush_debounced_track_change(self) -> None:
        candidate = self._pending_track_candidate
        if candidate is None:
            return
        if candidate.track_seq != self._current_track_seq:
            self.logger.debug(
                "Debounce fired but candidate stale candidate_seq=%s current_seq=%s",
                candidate.track_seq,
                self._current_track_seq,
            )
            return
        self.logger.info(
            "Debounce fired track_seq=%s track_key=%r -> scheduling lyrics lookup",
            candidate.track_seq,
            candidate.track_key,
        )
        self._enter_lyrics_loading_state()

        # Cache key intentionally stays artist+title to preserve existing cache behavior.
        self._queue_or_start_fetch(
            _QueuedFetch(
                track_seq=candidate.track_seq,
                track_key=candidate.track_key,
                artist=candidate.artist,
                title=candidate.title,
                force_network=False,
            )
        )

    def _queue_or_start_fetch(self, queued: _QueuedFetch) -> None:
        # Try cache first unless explicitly forcing network.
        cache_key = build_track_cache_key(queued.artist, queued.title)
        if not queued.force_network:
            cached = self.lyrics_cache.get(cache_key)
            if cached is not None:
                if queued.track_seq != self._current_track_seq or queued.track_key != self._current_track_key:
                    return
                self.logger.info("Cache hit: %s", cache_key)
                self.overlay.set_status_hint("")
                self._transient_retry_timer.stop()
                self._transient_retry_target = None
                self._failure_hold_timer.stop()
                self._pending_fallback_track_seq = -1
                self._pending_fallback_text = ""
                self._apply_lyrics_payload(cached.content, cached.is_synced)
                return
            self.logger.info("Cache miss: %s", cache_key)

        if self._fetch_inflight:
            self.logger.info(
                "Fetch inflight: queueing replacement track_seq=%s track_key=%r force_network=%s",
                queued.track_seq,
                queued.track_key,
                queued.force_network,
            )
            self._queued_fetch = queued
            self._cancel_active_fetch()
            return

        self.logger.info(
            "Fetch scheduled track_seq=%s track_key=%r force_network=%s",
            queued.track_seq,
            queued.track_key,
            queued.force_network,
        )
        self._start_fetch(queued)

    def _start_fetch(self, queued: _QueuedFetch) -> None:
        if queued.track_seq != self._current_track_seq or queued.track_key != self._current_track_key:
            return

        self._request_counter += 1
        request = _LyricsRequest(
            request_id=self._request_counter,
            track_seq=queued.track_seq,
            track_key=queued.track_key,
            artist=queued.artist,
            title=queued.title,
            cancel_event=threading.Event(),
            started_at=time.perf_counter(),
        )
        self._active_request = request
        self._fetch_inflight = True
        self.overlay.set_status_hint(f"Buscando letra... tentativa 1/{self._total_attempts()}")
        self.logger.info(
            "Lyrics request start request_id=%s track_seq=%s track_key=%r",
            request.request_id,
            request.track_seq,
            request.track_key,
        )

        future = self.executor.submit(self._fetch_lyrics_job, request)
        future.add_done_callback(lambda fut, req=request: self._emit_result_from_future(fut, req))

    def _cancel_active_fetch(self) -> None:
        if self._active_request is not None:
            self._active_request.cancel_event.set()

    def _fetch_lyrics_job(self, request: _LyricsRequest) -> dict:
        def progress(stage: str, attempt: int, total: int, message: str | None) -> None:
            self._fetch_progress_ready.emit(
                {
                    "request_id": request.request_id,
                    "track_seq": request.track_seq,
                    "track_key": request.track_key,
                    "stage": stage,
                    "attempt": attempt,
                    "total": total,
                    "message": message or "",
                }
            )

        result: LrclibResult = self.lrclib_client.search(
            request.artist,
            request.title,
            progress_callback=progress,
            cancel_event=request.cancel_event,
        )
        if (
            result.found
            and result.lyrics_text
            and not request.cancel_event.is_set()
            and request.track_seq == self._current_track_seq
            and request.track_key == self._current_track_key
        ):
            self.lyrics_cache.put(
                build_track_cache_key(request.artist, request.title),
                result.lyrics_text,
                is_synced=result.is_synced,
                artist=request.artist,
                title=request.title,
            )
        return {
            "request_id": request.request_id,
            "track_seq": request.track_seq,
            "track_key": request.track_key,
            "found": result.found,
            "lyrics_text": result.lyrics_text,
            "is_synced": result.is_synced,
            "message": result.message,
            "attempts": result.attempts,
            "transient_error": result.transient_error,
            "error_code": result.error_code,
            "outcome": result.outcome,
            "elapsed_ms": int((time.perf_counter() - request.started_at) * 1000),
        }

    def _emit_result_from_future(self, future: concurrent.futures.Future, request: _LyricsRequest) -> None:
        try:
            payload = future.result()
        except Exception:
            self.logger.exception("Unhandled exception in lyrics worker")
            payload = {
                "request_id": request.request_id,
                "track_seq": request.track_seq,
                "track_key": request.track_key,
                "found": False,
                "lyrics_text": "",
                "is_synced": False,
                "message": "Falha temporária ao buscar letra",
                "attempts": 0,
                "transient_error": True,
                "error_code": "worker_exception",
                "outcome": OUTCOME_FAIL_TRANSIENT_NETWORK,
                "elapsed_ms": int((time.perf_counter() - request.started_at) * 1000),
            }
        self._lyrics_result_ready.emit(payload)

    def _on_fetch_progress(self, payload_obj: object) -> None:
        if not isinstance(payload_obj, dict):
            return
        if payload_obj.get("track_seq") != self._current_track_seq:
            return
        if payload_obj.get("track_key") != self._current_track_key:
            return
        active = self._active_request
        if active is None or payload_obj.get("request_id") != active.request_id:
            return

        stage = str(payload_obj.get("stage") or "")
        attempt = int(payload_obj.get("attempt") or 0)
        total = max(1, int(payload_obj.get("total") or 1))

        if stage == "attempt":
            self.overlay.set_status_hint(f"Buscando letra... tentativa {attempt}/{total}")
        elif stage == "retry":
            retry_msg = self._friendly_retry_message(str(payload_obj.get("message") or ""))
            self.overlay.set_status_hint(f"{retry_msg} {min(attempt + 1, total)}/{total}")

    def _on_lyrics_result(self, payload_obj: object) -> None:
        if not isinstance(payload_obj, dict):
            return

        request_id = int(payload_obj.get("request_id") or -1)
        active = self._active_request
        if active is not None and request_id == active.request_id:
            self._fetch_inflight = False
            self._active_request = None
        self.logger.info(
            "Lyrics request done request_id=%s track_key=%r outcome=%s found=%s elapsed_ms=%s",
            request_id,
            payload_obj.get("track_key"),
            payload_obj.get("outcome"),
            payload_obj.get("found"),
            payload_obj.get("elapsed_ms"),
        )

        # Start latest queued fetch (if any) before applying result; only one active fetch at a time.
        queued = self._queued_fetch
        self._queued_fetch = None
        if queued is not None and (queued.track_seq == self._current_track_seq) and (queued.track_key == self._current_track_key):
            self._start_fetch(queued)

        # Silently discard stale/cancelled responses.
        if payload_obj.get("track_seq") != self._current_track_seq:
            self.logger.info(
                "Discarded stale response (track_seq) request_id=%s payload_seq=%s current_seq=%s",
                request_id,
                payload_obj.get("track_seq"),
                self._current_track_seq,
            )
            return
        if payload_obj.get("track_key") != self._current_track_key:
            self.logger.info(
                "Discarded stale response (track_key) request_id=%s payload_key=%r current_key=%r",
                request_id,
                payload_obj.get("track_key"),
                self._current_track_key,
            )
            return
        if payload_obj.get("error_code") == "cancelled":
            self.logger.info("Discarded cancelled response request_id=%s", request_id)
            return

        self._failure_hold_timer.stop()
        self._pending_fallback_track_seq = -1
        self._pending_fallback_text = ""
        self._transient_retry_timer.stop()
        self._transient_retry_target = None

        outcome = str(payload_obj.get("outcome") or "")
        if not payload_obj.get("found"):
            transient_error = bool(payload_obj.get("transient_error"))
            message = str(payload_obj.get("message") or "Falha temporária ao buscar letra")
            self.logger.info(
                "Lyrics fetch failed (transient=%s code=%s track=%s): %s",
                transient_error,
                payload_obj.get("error_code"),
                self._current_track_key,
                message,
            )
            if outcome == OUTCOME_FAIL_TRANSIENT_NETWORK or transient_error:
                self.overlay.set_status_hint(self._friendly_retry_message(message))
                # Keep loading state visible while retry is pending; do not restore old lyric.
                self.overlay.set_lyric_text("Buscando letra...")
                self._schedule_transient_retry()
                return

            self.overlay.set_status_hint("Letra indisponível")
            self._schedule_fallback_text("Letra não encontrada.")
            return

        self.overlay.set_status_hint("")
        self._transient_retry_timer.stop()
        self._transient_retry_target = None
        if outcome == OUTCOME_SUCCESS_NO_SYNCED:
            self._apply_unsynced_success()
            return
        self._apply_lyrics_payload(
            lyrics_text=str(payload_obj.get("lyrics_text", "")),
            declared_synced=bool(payload_obj.get("is_synced", False)),
        )

    def _schedule_transient_retry(self) -> None:
        if not self._current_media.is_active or not self._is_fetchable_track(self._current_media):
            return
        self._transient_retry_target = _QueuedFetch(
            track_seq=self._current_track_seq,
            track_key=self._current_track_key,
            artist=self._current_media.artist,
            title=self._current_media.title,
            force_network=True,
        )
        self._transient_retry_timer.start(TRANSIENT_RETRY_DELAY_MS)
        self.logger.info(
            "Scheduled transient retry track_seq=%s track_key=%r delay_ms=%s",
            self._current_track_seq,
            self._current_track_key,
            TRANSIENT_RETRY_DELAY_MS,
        )

    def _run_transient_retry(self) -> None:
        target = self._transient_retry_target
        self._transient_retry_target = None
        if target is None:
            return
        if target.track_seq != self._current_track_seq or target.track_key != self._current_track_key:
            self.logger.info("Transient retry skipped due to track change")
            return
        self.logger.info(
            "Transient retry firing track_seq=%s track_key=%r",
            target.track_seq,
            target.track_key,
        )
        self._queue_or_start_fetch(target)

    def _schedule_fallback_text(self, text: str) -> None:
        keep_line = bool(self._last_good_lyric_line) and ((time.time() - self._last_good_lyric_at) <= GOOD_LINE_FRESH_SECONDS)
        self._pending_fallback_track_seq = self._current_track_seq
        self._pending_fallback_text = text
        if keep_line:
            self._failure_hold_timer.start(FAILURE_HOLD_MS)
            return
        self.overlay.set_lyric_text(text)
        self.overlay.set_status_hint("")
        self._last_lyric_line = text

    def _apply_pending_fallback(self) -> None:
        if self._pending_fallback_track_seq != self._current_track_seq:
            return
        if not self._pending_fallback_text:
            return
        self.overlay.set_lyric_text(self._pending_fallback_text)
        self.overlay.set_status_hint("")
        self._last_lyric_line = self._pending_fallback_text
        self._pending_fallback_text = ""
        self._pending_fallback_track_seq = -1

    def _apply_lyrics_payload(self, lyrics_text: str, declared_synced: bool) -> None:
        parsed = parse_lrc(lyrics_text)
        if declared_synced and parsed.is_synced and parsed.lines:
            self.logger.info("Synced lyrics parsed successfully lines=%s text_len=%s", len(parsed.lines), len(lyrics_text))
            self.sync.load(parsed)
            self._last_lyric_line = ""
            self._update_synced_lyric_line(force=True)
            return
        if declared_synced and not parsed.lines:
            first_ts = TIMESTAMP_IN_TEXT_RE.search(lyrics_text or "")
            self.logger.warning(
                "Synced lyrics payload could not be parsed lines=0 text_len=%s first_timestamp=%r",
                len(lyrics_text or ""),
                first_ts.group(1) if first_ts else None,
            )
            self.sync.clear()
            self._last_lyric_line = "Letra indisponível."
            self.overlay.set_lyric_text(self._last_lyric_line)
            self.overlay.set_status_hint("")
            return

        self.sync.clear()
        self._apply_unsynced_success()

    def _enter_lyrics_loading_state(self) -> None:
        # Debounce confirmed a real track change: stop syncing previous LRC and show loading.
        self.sync.clear()
        self._clear_paused_lyric_latch("loading")
        self._clear_paused_position_latch("loading")
        self._last_lyric_line = ""
        self._failure_hold_timer.stop()
        self._pending_fallback_track_seq = -1
        self._pending_fallback_text = ""
        self.overlay.set_lyric_text("Buscando letra...")

    def _apply_unsynced_success(self) -> None:
        fallback = self._friendly_no_synced_message()
        self.logger.info("Applying SUCCESS_NO_SYNCED message")
        self._last_lyric_line = fallback
        self.overlay.set_lyric_text(fallback)
        self.overlay.set_status_hint("")

    def _update_synced_lyric_line(
        self,
        force: bool = False,
        *,
        position_seconds: float | None = None,
        effective_playing: bool | None = None,
    ) -> None:
        if not self.sync.has_synced():
            self._was_effective_playing = (
                self._playback_clock.is_playing if effective_playing is None else bool(effective_playing)
            )
            return
        if effective_playing is None:
            effective_playing = self._playback_clock.is_playing
        if not effective_playing:
            if self._latched_paused_line is None:
                line = self._last_lyric_line
                if not line:
                    pos_est = (
                        self._playback_clock.estimated_position()
                        if position_seconds is None
                        else float(position_seconds)
                    )
                    line = self.sync.current_line(
                        playback_position=pos_est,
                        offset_seconds=self.config.lyrics.offset_seconds,
                    )
                self._latched_paused_line = line or ""
                self.logger.debug("lyrics_pause_latch line=%r", self._latched_paused_line)
            shown = self._latched_paused_line or "..."
            if force or self._last_lyric_line != (self._latched_paused_line or ""):
                self._last_lyric_line = self._latched_paused_line or ""
                self.overlay.set_lyric_text(shown)
            self._was_effective_playing = False
            return
        if self._latched_paused_line is not None:
            self._clear_paused_lyric_latch("playing")
        pos_est = self._playback_clock.estimated_position() if position_seconds is None else float(position_seconds)
        line = self.sync.current_line(
            playback_position=pos_est,
            offset_seconds=self.config.lyrics.offset_seconds,
        )
        if not force and line == self._last_lyric_line:
            return
        self._last_lyric_line = line
        shown = line or "..."
        self.overlay.set_lyric_text(shown)
        if line:
            self._last_good_lyric_line = line
            self._last_good_lyric_at = time.time()
        self._was_effective_playing = True

    def _clear_paused_lyric_latch(self, reason: str) -> None:
        if self._latched_paused_line is not None:
            self.logger.debug("lyrics_pause_unlatch reason=%s", reason)
        self._latched_paused_line = None

    def _clear_paused_position_latch(self, reason: str) -> None:
        if self._latched_paused_position is not None:
            self.logger.debug("time_pause_unlatch reason=%s", reason)
        self._latched_paused_position = None

    def force_reload_current_track(self) -> None:
        if not self._current_media.is_active or not self._is_fetchable_track(self._current_media):
            return
        self.sync.clear()
        self._last_lyric_line = ""
        self._failure_hold_timer.stop()
        self._pending_fallback_text = ""
        self._queued_fetch = None
        self._cancel_active_fetch()
        queued = _QueuedFetch(
            track_seq=self._current_track_seq,
            track_key=self._current_track_key,
            artist=self._current_media.artist,
            title=self._current_media.title,
            force_network=True,
        )
        self._queue_or_start_fetch(queued)

    def _toggle_overlay_visibility(self) -> None:
        self._overlay_visible = not self._overlay_visible
        if self._overlay_visible:
            self.overlay.show()
        else:
            self.overlay.hide()

    def _open_cache_folder(self) -> None:
        self.tray.open_folder(str(self.paths.cache_dir))

    def _reload_config_from_disk(self) -> None:
        try:
            new_config = load_config(self.paths)
        except Exception:
            self.logger.exception("Falha ao recarregar config do disco")
            self.overlay.set_status_hint("Falha ao recarregar config")
            return
        self._apply_loaded_config(new_config)
        self.overlay.set_status_hint("Config recarregada")
        QTimer.singleShot(1500, lambda: self.overlay.set_status_hint(""))

    def _friendly_retry_message(self, detail: str) -> str:
        text = (detail or "").lower()
        if "timeout" in text or "tempo de resposta" in text or "conexão esgotado" in text:
            return "Falha de rede (timeout). Tentando novamente..."
        return "Falha temporária de conexão. Tentando novamente..."

    def _friendly_network_fail_overlay_message(self, detail: str) -> str:
        text = (detail or "").lower()
        if "timeout" in text or "tempo de resposta" in text:
            return "Falha de rede (timeout). Tentando novamente..."
        return "Falha temporária de conexão. Tentando novamente..."

    def _friendly_no_synced_message(self) -> str:
        configured = (self.config.lyrics.fallback_unsynced_text or "").strip()
        return configured or DEFAULT_NO_SYNCED_TEXT

    def _apply_loaded_config(self, new_config: AppConfig) -> None:
        self.config = new_config
        self._apply_clock_config()
        self.overlay.apply_config(self.config)
        self.lyrics_cache.resize(self.config.cache.max_entries)
        self.lrclib_client.timeout = (
            self.config.network.lrclib_timeout_connect,
            self.config.network.lrclib_timeout_read,
        )
        self.lrclib_client.max_retries = max(0, int(self.config.network.lrclib_max_retries))
        self.lrclib_client.backoff_base_seconds = max(0.1, float(self.config.network.lrclib_backoff_base_seconds))
        self.media_service.set_poll_interval_ms(self.config.lyrics.update_interval_ms)
        if self._settings_window is not None:
            self._settings_window.load_from_config(self.config)

    def _apply_clock_config(self) -> None:
        ui_timer_ms = max(50, int(getattr(self.config.clock, "ui_timer_ms", 80)))
        self._ui_clock_timer.setInterval(ui_timer_ms)
        if self._started and (not self._ui_clock_timer.isActive()):
            self._ui_clock_timer.start()
        self._playback_clock.configure(
            seek_threshold_s=float(getattr(self.config.clock, "seek_threshold_s", 1.2)),
            enable_soft_correction=bool(getattr(self.config.clock, "enable_soft_correction", False)),
            soft_correction_gain=float(getattr(self.config.clock, "soft_correction_gain", 0.15)),
            soft_correction_clamp_s=float(getattr(self.config.clock, "soft_correction_clamp_s", 0.8)),
        )

    def _open_settings_window(self) -> None:
        if self._settings_window is None:
            self._settings_window = SettingsWindow(self.config)
            self._settings_window.save_requested.connect(self._save_from_settings)
            self._settings_window.destroyed.connect(lambda *_: setattr(self, "_settings_window", None))
        else:
            self._settings_window.load_from_config(self.config)
        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def _save_from_settings(self, payload_obj: object) -> None:
        if not isinstance(payload_obj, SettingsValues):
            return
        self.config.font.family = payload_obj.font_family
        self.config.font.size = int(payload_obj.font_size)
        self.config.font.color = payload_obj.font_color
        self.config.font.shadow.enabled = bool(payload_obj.shadow_enabled)
        self.config.font.shadow.color = payload_obj.shadow_color
        self.config.lyrics.offset_seconds = float(payload_obj.offset_seconds)
        self.config.lyrics.language = payload_obj.language
        self.config.overlay.layout_preset = payload_obj.layout_preset
        self.config.overlay.click_through = bool(payload_obj.click_through)
        self.config.overlay.snap_to_taskbar = bool(payload_obj.snap_to_taskbar)

        save_config(self.paths, self.config)
        self.overlay.apply_config(self.config)
        self.overlay.set_status_hint("Config salva")
        QTimer.singleShot(1500, lambda: self.overlay.set_status_hint(""))

    def _on_position_committed(self, payload_obj: object) -> None:
        if not isinstance(payload_obj, PositionPayload):
            return
        self.config.set_saved_position(
            screen_name=payload_obj.screen_name,
            scale_percent=payload_obj.scale_percent,
            screen_width=payload_obj.screen_width,
            screen_height=payload_obj.screen_height,
            x=payload_obj.x,
            y=payload_obj.y,
        )
        save_config(self.paths, self.config)
