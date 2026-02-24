from __future__ import annotations

import logging
import re
import time
from bisect import bisect_right
from dataclasses import dataclass, field


TIMESTAMP_RE = re.compile(r"\[(\d{1,2}:\d{2}(?:\.\d{1,3})?)\]")
METADATA_RE = re.compile(r"^\[(ar|ti|al|by|offset):", re.IGNORECASE)
SEEK_BACKWARD_THRESHOLD_SECONDS = 1.0
LINE_SWITCH_LEAD_IN_SECONDS = 0.08
DEBUG_SAMPLE_SECONDS = 0.5

logger = logging.getLogger("stzlyrics_overlay.sync")


@dataclass(slots=True)
class LyricLine:
    time_seconds: float
    text: str


@dataclass(slots=True)
class ParsedLyrics:
    is_synced: bool
    lines: list[LyricLine] = field(default_factory=list)
    plain_text: str = ""

    @property
    def first_plain_line(self) -> str:
        source = self.plain_text or "\n".join(line.text for line in self.lines)
        for raw in source.splitlines():
            text = raw.strip()
            if text:
                return text
        return ""


def parse_timestamp(timestamp: str) -> float:
    minutes_str, seconds_str = timestamp.split(":", 1)
    minutes = int(minutes_str)
    seconds = float(seconds_str)
    return (minutes * 60.0) + seconds


def parse_lrc(text: str) -> ParsedLyrics:
    if not text:
        return ParsedLyrics(is_synced=False, plain_text="")

    parsed_lines: list[LyricLine] = []
    plain_accumulator: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        stripped = line.strip()
        if not stripped:
            continue

        if METADATA_RE.match(stripped):
            continue

        timestamps = TIMESTAMP_RE.findall(line)
        if not timestamps:
            plain_accumulator.append(stripped)
            continue

        lyric_text = TIMESTAMP_RE.sub("", line).strip()
        for ts in timestamps:
            parsed_lines.append(LyricLine(time_seconds=parse_timestamp(ts), text=lyric_text))

    if parsed_lines:
        parsed_lines.sort(key=lambda item: item.time_seconds)
        return ParsedLyrics(is_synced=True, lines=parsed_lines, plain_text=text)

    return ParsedLyrics(is_synced=False, plain_text="\n".join(plain_accumulator) or text)


class LyricsSynchronizer:
    """Incremental cursor to avoid scanning the full LRC on every tick."""

    def __init__(self) -> None:
        self._lines: list[LyricLine] = []
        self._times: list[float] = []
        self._current_index: int = 0
        self._last_position: float = -1.0
        self._last_debug_log_at: float = 0.0

    def load(self, lyrics: ParsedLyrics) -> None:
        self._lines = list(lyrics.lines) if lyrics.is_synced else []
        self._times = [line.time_seconds for line in self._lines]
        self._current_index = 0
        self._last_position = -1.0
        self._last_debug_log_at = 0.0

    def clear(self) -> None:
        self._lines = []
        self._times = []
        self._current_index = 0
        self._last_position = -1.0
        self._last_debug_log_at = 0.0

    def has_synced(self) -> bool:
        return bool(self._lines)

    def current_line(self, playback_position: float, offset_seconds: float = 0.0) -> str:
        if not self._lines:
            return ""

        pos = max(0.0, float(playback_position) + float(offset_seconds))
        total = len(self._lines)

        if self._current_index < 0 or self._current_index >= total:
            self._current_index = 0

        if self._last_position >= 0.0 and pos < self._last_position:
            delta = pos - self._last_position
            backward = -delta
            if backward > SEEK_BACKWARD_THRESHOLD_SECONDS:
                self._current_index = self._find_index_for_position(pos)
                logger.debug(
                    "Lyrics sync seek detected last_pos=%.3f pos=%.3f delta=%.3f new_index=%s",
                    self._last_position,
                    pos,
                    delta,
                    self._current_index,
                )
            else:
                # Ignore small backward jitter and keep the current line/index stable.
                pos = self._last_position

        while (
            self._current_index < total - 1
            and pos >= (self._lines[self._current_index + 1].time_seconds - LINE_SWITCH_LEAD_IN_SECONDS)
        ):
            self._current_index += 1

        self._last_position = pos
        text = self._lines[self._current_index].text
        self._debug_sync_tick(playback_position, offset_seconds, pos)
        # Keep empty timed lines as empty (instrumental gaps) instead of
        # falling back to an unrelated lyric from elsewhere in the file.
        return text or ""

    def current_index(self) -> int:
        if not self._lines:
            return -1
        total = len(self._lines)
        if self._current_index < 0:
            return 0
        if self._current_index >= total:
            return total - 1
        return self._current_index

    def context_window(self, before: int, after: int) -> tuple[list[str], int, int]:
        if not self._lines:
            return [], 0, -1
        before_n = max(0, int(before))
        after_n = max(0, int(after))
        current_idx = self.current_index()
        slot_current = before_n
        items: list[str] = []
        for rel in range(-before_n, after_n + 1):
            idx = current_idx + rel
            if 0 <= idx < len(self._lines):
                items.append(self._lines[idx].text or "")
            else:
                items.append("")
        return items, slot_current, current_idx

    def _find_index_for_position(self, pos: float) -> int:
        if not self._times:
            return 0
        idx = bisect_right(self._times, pos + LINE_SWITCH_LEAD_IN_SECONDS) - 1
        if idx < 0:
            return 0
        if idx >= len(self._times):
            return len(self._times) - 1
        return idx

    def _debug_sync_tick(self, playback_position: float, offset_seconds: float, pos_used: float) -> None:
        now = time.monotonic()
        if (now - self._last_debug_log_at) < DEBUG_SAMPLE_SECONDS:
            return
        self._last_debug_log_at = now
        cur_ts = self._times[self._current_index] if self._times else None
        next_ts = self._times[self._current_index + 1] if (self._current_index + 1) < len(self._times) else None
        logger.debug(
            "sync_tick pos_raw=%.3f offset=%.3f pos_used=%.3f idx=%s ts_cur=%s ts_next=%s last_pos=%.3f",
            float(playback_position),
            float(offset_seconds),
            pos_used,
            self._current_index,
            f"{cur_ts:.3f}" if cur_ts is not None else "None",
            f"{next_ts:.3f}" if next_ts is not None else "None",
            self._last_position,
        )
