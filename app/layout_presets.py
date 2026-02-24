from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LayoutPreset(str, Enum):
    DETAILED = "detailed"
    MINIMAL = "minimal"
    CONTEXT_2_2 = "context_2_2"  # placeholder for future preset


@dataclass(frozen=True, slots=True)
class LayoutRenderModel:
    preset: LayoutPreset
    show_header: bool
    header_height: int
    header_gap: int


def normalize_layout_preset(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw == LayoutPreset.MINIMAL.value:
        return LayoutPreset.MINIMAL.value
    return LayoutPreset.DETAILED.value


def build_layout_render_model(preset_value: str | None) -> LayoutRenderModel:
    preset = LayoutPreset(normalize_layout_preset(preset_value))
    if preset == LayoutPreset.MINIMAL:
        return LayoutRenderModel(
            preset=preset,
            show_header=False,
            header_height=0,
            header_gap=0,
        )
    return LayoutRenderModel(
        preset=LayoutPreset.DETAILED,
        show_header=True,
        header_height=18,
        header_gap=2,
    )

