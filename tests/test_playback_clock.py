from dataclasses import dataclass

from app.playback_clock import PlaybackClock


@dataclass
class FakeState:
    """Minimal stand-in for MediaState exposing only what PlaybackClock reads.

    Kept Qt-free so the clock can be tested without importing PySide6.
    """

    position_seconds: float
    duration_seconds: float = 200.0
    playback_status: str = "Playing"
    title: str = "Song"

    @property
    def is_playing(self) -> bool:
        return self.playback_status.lower() == "playing"

    @property
    def track_key(self) -> str:
        return f"Artist|{self.title}|{int(round(self.duration_seconds))}"


def _state(*, pos, status="Playing", duration=200.0, title="Song"):
    return FakeState(
        position_seconds=pos,
        duration_seconds=duration,
        playback_status=status,
        title=title,
    )


def test_init_anchors_to_raw_position():
    clock = PlaybackClock()
    result = clock.apply_state(_state(pos=10.0), now_mono=100.0)

    assert result.reset_reason == "track_change"
    assert clock.initialized is True
    assert clock.is_playing is True
    # No elapsed time yet -> estimate equals the anchor.
    assert clock.estimated_position(now_mono=100.0) == 10.0


def test_playing_estimate_advances_with_monotonic_time():
    clock = PlaybackClock()
    clock.apply_state(_state(pos=10.0), now_mono=100.0)

    # 5 seconds of wall-clock pass with no new raw report.
    assert clock.estimated_position(now_mono=105.0) == 15.0


def test_track_change_reanchors():
    clock = PlaybackClock()
    clock.apply_state(_state(pos=50.0, title="A"), now_mono=100.0)
    result = clock.apply_state(_state(pos=0.0, title="B"), now_mono=101.0)

    assert result.reset_reason == "track_change"
    assert clock.estimated_position(now_mono=101.0) == 0.0


def test_forward_seek_reanchors():
    clock = PlaybackClock()
    clock.apply_state(_state(pos=10.0), now_mono=100.0)
    # Raw jumps far ahead of the estimate -> treated as a seek, not jitter.
    result = clock.apply_state(_state(pos=80.0), now_mono=101.0)

    assert result.reset_reason == "seek_reanchor"
    assert clock.estimated_position(now_mono=101.0) == 80.0


def test_frozen_raw_position_is_ignored_while_playing():
    clock = PlaybackClock()
    clock.apply_state(_state(pos=10.0), now_mono=100.0)
    # Estimate is ~13s after 3s of playback, but GSMTC still reports the stale 10s.
    result = clock.apply_state(_state(pos=10.0), now_mono=103.0)

    assert result.raw_ignored is True
    assert result.reset_reason == "raw_ignored_backward_lag"
    # The estimate keeps moving forward rather than being dragged back to 10s.
    assert clock.estimated_position(now_mono=103.0) >= 13.0 - 0.01


def test_explicit_pause_freezes_estimate():
    clock = PlaybackClock()
    clock.apply_state(_state(pos=10.0), now_mono=100.0)
    result = clock.apply_state(_state(pos=15.0, status="Paused"), now_mono=105.0)

    assert result.reset_reason == "pause_anchor"
    assert clock.is_playing is False
    # Frozen: time passing no longer advances the estimate.
    frozen = clock.estimated_position(now_mono=110.0)
    assert frozen == clock.estimated_position(now_mono=120.0)


def test_reset_inactive_clears_state():
    clock = PlaybackClock()
    clock.apply_state(_state(pos=10.0), now_mono=100.0)
    clock.reset_inactive()

    assert clock.initialized is False
    assert clock.is_playing is False
    assert clock.estimated_position(now_mono=200.0) == 0.0
