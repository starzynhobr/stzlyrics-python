from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_key_part(value: str) -> str:
    normalized = " ".join((value or "").strip().lower().split())
    return normalized


def build_track_cache_key(artist: str, title: str) -> str:
    return f"{_normalize_key_part(artist)} - {_normalize_key_part(title)}"


@dataclass(slots=True)
class CacheEntry:
    key: str
    file_name: str
    is_synced: bool
    last_access: str
    hit_count: int
    fetched_at: str
    artist: str = ""
    title: str = ""

    @classmethod
    def from_dict(cls, key: str, raw: dict[str, Any]) -> CacheEntry:
        return cls(
            key=key,
            file_name=str(raw.get("file_name") or raw.get("fileName")),
            is_synced=bool(raw.get("is_synced", raw.get("isSynced", False))),
            last_access=str(raw.get("last_access", raw.get("lastAccess", _utc_now_iso()))),
            hit_count=int(raw.get("hit_count", raw.get("hitCount", 0))),
            fetched_at=str(raw.get("fetched_at", raw.get("fetchedAt", _utc_now_iso()))),
            artist=str(raw.get("artist", "")),
            title=str(raw.get("title", "")),
        )

    def to_index_dict(self) -> dict[str, Any]:
        return {
            "fileName": self.file_name,
            "isSynced": self.is_synced,
            "lastAccess": self.last_access,
            "hitCount": self.hit_count,
            "fetchedAt": self.fetched_at,
            "artist": self.artist,
            "title": self.title,
        }


@dataclass(slots=True)
class CachedLyrics:
    key: str
    content: str
    is_synced: bool
    entry: CacheEntry


class LyricsCache:
    def __init__(self, cache_dir: Path, index_file: Path, max_entries: int = 100) -> None:
        self.cache_dir = cache_dir
        self.index_file = index_file
        self.max_entries = max(1, int(max_entries))
        self._lock = threading.Lock()
        self._index: dict[str, CacheEntry] = {}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._load_index()

    def _load_index(self) -> None:
        if not self.index_file.exists():
            return
        try:
            raw = json.loads(self.index_file.read_text(encoding="utf-8"))
            entries_raw = raw.get("entries", {}) if isinstance(raw, dict) else {}
            if isinstance(entries_raw, dict):
                for key, entry_raw in entries_raw.items():
                    if isinstance(entry_raw, dict):
                        self._index[key] = CacheEntry.from_dict(key, entry_raw)
        except Exception:
            self._index = {}

    def _save_index(self) -> None:
        payload = {
            "schemaVersion": 1,
            "updatedAt": _utc_now_iso(),
            "entries": {key: entry.to_index_dict() for key, entry in self._index.items()},
        }
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.index_file.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self.index_file)

    def _evict_if_needed(self) -> None:
        if len(self._index) <= self.max_entries:
            return
        victims = sorted(
            self._index.values(),
            key=lambda e: (e.last_access, e.hit_count, e.fetched_at),
        )
        while len(self._index) > self.max_entries and victims:
            victim = victims.pop(0)
            self._index.pop(victim.key, None)
            try:
                (self.cache_dir / victim.file_name).unlink(missing_ok=True)
            except Exception:
                pass

    def _build_file_name(self, key: str, is_synced: bool) -> str:
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()  # noqa: S324 - cache key only
        return f"{digest}.{'lrc' if is_synced else 'txt'}"

    def get(self, key: str) -> CachedLyrics | None:
        with self._lock:
            entry = self._index.get(key)
            if not entry:
                return None

            file_path = self.cache_dir / entry.file_name
            if not file_path.exists():
                self._index.pop(key, None)
                self._save_index()
                return None

            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                return None

            entry.hit_count += 1
            entry.last_access = _utc_now_iso()
            self._save_index()
            return CachedLyrics(key=key, content=content, is_synced=entry.is_synced, entry=entry)

    def put(self, key: str, content: str, is_synced: bool, artist: str = "", title: str = "") -> None:
        file_name = self._build_file_name(key, is_synced=is_synced)
        file_path = self.cache_dir / file_name

        with self._lock:
            file_path.write_text(content, encoding="utf-8")
            now = _utc_now_iso()
            existing_hits = self._index.get(key).hit_count if key in self._index else 0
            self._index[key] = CacheEntry(
                key=key,
                file_name=file_name,
                is_synced=is_synced,
                last_access=now,
                hit_count=existing_hits + 1,
                fetched_at=now,
                artist=artist,
                title=title,
            )
            self._evict_if_needed()
            self._save_index()

    def resize(self, max_entries: int) -> None:
        with self._lock:
            self.max_entries = max(1, int(max_entries))
            self._evict_if_needed()
            self._save_index()

    def clear(self) -> None:
        with self._lock:
            self._index = {}
            for pattern in ("*.lrc", "*.txt"):
                for file_path in self.cache_dir.glob(pattern):
                    try:
                        file_path.unlink(missing_ok=True)
                    except Exception:
                        pass
            try:
                self.index_file.unlink(missing_ok=True)
            except Exception:
                pass
            self._save_index()
