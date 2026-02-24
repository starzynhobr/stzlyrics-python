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
    context_before: int = 0
    context_after: int = 0
    context_line_gap: int = 4
    animate_context_transition: bool = False
    context_anim_duration_ms: int = 220


def normalize_layout_preset(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw == LayoutPreset.MINIMAL.value:
        return LayoutPreset.MINIMAL.value
    if raw == LayoutPreset.CONTEXT_2_2.value:
        return LayoutPreset.CONTEXT_2_2.value
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
    if preset == LayoutPreset.CONTEXT_2_2:
        return LayoutRenderModel(
            preset=preset,
            show_header=False,
            header_height=0,
            header_gap=0,
            context_before=2,
            context_after=2,
            context_line_gap=4,
            animate_context_transition=True,
            context_anim_duration_ms=220,
        )
    return LayoutRenderModel(
        preset=LayoutPreset.DETAILED,
        show_header=True,
        header_height=18,
        header_gap=2,
    )
