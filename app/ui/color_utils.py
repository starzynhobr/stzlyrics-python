from __future__ import annotations

import re
from typing import Tuple

from PySide6.QtGui import QColor


_HEX_RE = re.compile(r"^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def parse_rgba_hex(value: str) -> Tuple[int, int, int, int]:
    """Parse #RRGGBB or #RRGGBBAA and return RGBA tuple."""
    text = (value or "").strip()
    match = _HEX_RE.fullmatch(text)
    if not match:
        raise ValueError("Invalid RGBA hex format")
    hex_part = match.group(1)
    if len(hex_part) == 6:
        hex_part = f"{hex_part}FF"
    r = int(hex_part[0:2], 16)
    g = int(hex_part[2:4], 16)
    b = int(hex_part[4:6], 16)
    a = int(hex_part[6:8], 16)
    return r, g, b, a


def qcolor_from_rgba_hex(value: str, fallback: str) -> QColor:
    try:
        r, g, b, a = parse_rgba_hex(value)
    except ValueError:
        r, g, b, a = parse_rgba_hex(fallback)
    return QColor(r, g, b, a)


def rgba_hex_from_qcolor(color: QColor) -> str:
    if not color.isValid():
        color = QColor(255, 255, 255, 255)
    return "#{:02X}{:02X}{:02X}{:02X}".format(
        color.red(),
        color.green(),
        color.blue(),
        color.alpha(),
    )


def normalize_rgba_hex(value: str, fallback: str) -> str:
    try:
        r, g, b, a = parse_rgba_hex(value)
    except ValueError:
        r, g, b, a = parse_rgba_hex(fallback)
    return "#{:02X}{:02X}{:02X}{:02X}".format(r, g, b, a)

