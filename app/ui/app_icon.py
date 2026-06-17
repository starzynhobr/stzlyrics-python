from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon


def _asset_candidates(file_names: list[str]) -> list[Path]:
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass) / "app" / "assets"
        candidates.extend(base / name for name in file_names)
    base_dev = Path(__file__).resolve().parents[1] / "assets"
    candidates.extend(base_dev / name for name in file_names)
    return candidates


def _first_existing(candidates: list[Path]) -> Path | None:
    for path in candidates:
        try:
            if path.exists():
                return path
        except Exception:
            continue
    return None


def app_icon_path() -> Path | None:
    return _first_existing(_asset_candidates(["stz-lyrics.png", "logo.ico"]))


def tray_icon_path() -> Path | None:
    return _first_existing(_asset_candidates(["stz-lyrics.png", "logo_tray.ico", "logo64-64.ico", "logo.ico"]))


def load_app_icon() -> QIcon:
    path = app_icon_path()
    if path is None:
        return QIcon()
    return QIcon(str(path))


def load_tray_icon() -> QIcon:
    path = tray_icon_path()
    if path is None:
        return QIcon()
    return QIcon(str(path))
