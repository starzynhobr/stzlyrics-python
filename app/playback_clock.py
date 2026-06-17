"""Smoothing playback clock that turns jittery GSMTC timeline reports into a
stable, monotonic position estimate.

GSMTC (notably Spotify) can freeze the reported timeline position for several
polls and then jump forward, and can flip play/pause state spuriously. This
module isolates that handling from the controller so it can be unit-tested in
isolation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.media_session import MediaState

CLOCK_BACKWARD_LAG_IGNORE_SECONDS = 0.30
CLOCK_PLAYING_PROGRESS_GRACE_SECONDS = 1.2
CLOCK_PLAY_STATE_HYSTERESIS_POLLS = 2
# Ignore tiny raw jitter from GSMTC (especially while paused).
CLOCK_RAW_PROGRESS_EPSILON_SECONDS = 0.20


@dataclass(slots=True)
class ClockUpdateResult:
    raw_pos: float
    est_before: float
    est_after: float
    err: float
    reset_reason: str = ""
    raw_ignored: bool = False


class PlaybackClock:
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

    def apply_state(self, state: MediaState, now_mono: float | None = None) -> ClockUpdateResult:
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
            return ClockUpdateResult(
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
                return ClockUpdateResult(
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
            return ClockUpdateResult(
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
            return ClockUpdateResult(
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
            return ClockUpdateResult(
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
        return ClockUpdateResult(
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
