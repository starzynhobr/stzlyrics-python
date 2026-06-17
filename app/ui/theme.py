from __future__ import annotations

import sys
from pathlib import Path

# JaxCore-inspired accent. Kept here so it can later be driven by the user's
# lyric color; for now it is a fixed token injected into the .qss.
ACCENT_COLOR = "#ff5a1f"
ACCENT_COLOR_HOVER = "#ff6f3d"


def load_stylesheet() -> str:
    """Load the dark theme .qss and inject the accent tokens.

    Returns an empty string if the file can't be found (widgets still work,
    just fall back to the default Qt look).
    """
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "app" / "assets" / "style.qss")
    candidates.append(Path(__file__).resolve().parents[1] / "assets" / "style.qss")
    for path in candidates:
        try:
            if path.exists():
                qss = path.read_text(encoding="utf-8")
                return qss.replace("{ACCENT_HOVER}", ACCENT_COLOR_HOVER).replace("{ACCENT}", ACCENT_COLOR)
        except Exception:
            continue
    return ""
