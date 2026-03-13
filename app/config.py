from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.layout_presets import normalize_context_animation_style, normalize_layout_preset

APP_NAME = "STZLyricsOverlay"


def _appdata_root() -> Path:
    base = os.getenv("APPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / f".{APP_NAME.lower()}"


@dataclass
class AppPaths:
    root: Path
    config_file: Path
    cache_dir: Path
    logs_dir: Path
    cache_index_file: Path

    @classmethod
    def default(cls) -> "AppPaths":
        root = _appdata_root()
        return cls(
            root=root,
            config_file=root / "config.json",
            cache_dir=root / "cache",
            logs_dir=root / "logs",
            cache_index_file=root / "cache" / "index.json",
        )

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class ShadowConfig:
    enabled: bool = True
    color: str = "#000000"
    offset_x: int = 1
    offset_y: int = 1


@dataclass
class FontConfig:
    family: str = "Segoe UI"
    size: int = 28
    color: str = "#FFFFFF"
    preset_colors: dict[str, str] = field(default_factory=dict)
    track_size: int = 12
    track_color: str = "#C8C8C8"
    shadow: ShadowConfig = field(default_factory=ShadowConfig)


@dataclass
class OverlayConfig:
    width: int = 960
    height: int = 84
    padding_x: int = 18
    padding_y: int = 8
    click_through: bool = False
    snap_to_taskbar: bool = True
    snap_threshold: int = 20
    always_on_top: bool = True
    always_on_top_by_preset: dict[str, bool] = field(default_factory=dict)
    context_animation_style: str = "slide"
    start_with_windows: bool = False
    layout_preset: str = "detailed"
    positions: dict[str, dict[str, int]] = field(default_factory=dict)


@dataclass
class LyricsConfig:
    offset_seconds: float = 0.10
    update_interval_ms: int = 300
    fallback_unsynced_text: str = "Sem letra sincronizada"
    language: str = "PT-BR"


@dataclass
class CacheConfig:
    max_entries: int = 500


@dataclass
class NetworkConfig:
    lrclib_timeout_connect: float = 3.0
    lrclib_timeout_read: float = 20.0
    lrclib_max_retries: int = 2
    lrclib_backoff_base_seconds: float = 0.6


@dataclass
class ClockConfig:
    ui_timer_ms: int = 80
    seek_threshold_s: float = 1.2
    enable_soft_correction: bool = False
    soft_correction_gain: float = 0.15
    soft_correction_clamp_s: float = 0.8
    debug_clock_overlay: bool = False


@dataclass
class AppConfig:
    font: FontConfig = field(default_factory=FontConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    lyrics: LyricsConfig = field(default_factory=LyricsConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    clock: ClockConfig = field(default_factory=ClockConfig)

    @staticmethod
    def _merge_dataclass(dc_type, raw: dict[str, Any]):
        kwargs: dict[str, Any] = {}
        for field_def in dc_type.__dataclass_fields__.values():  # type: ignore[attr-defined]
            name = field_def.name
            default_value = getattr(dc_type(), name)
            value = raw.get(name, default_value) if isinstance(raw, dict) else default_value
            if hasattr(field_def.type, "__dataclass_fields__") and isinstance(value, dict):
                kwargs[name] = AppConfig._merge_dataclass(field_def.type, value)
            elif name == "shadow" and isinstance(value, dict):
                kwargs[name] = AppConfig._merge_dataclass(ShadowConfig, value)
            else:
                kwargs[name] = value
        return dc_type(**kwargs)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AppConfig":
        config = cls(
            font=cls._merge_dataclass(FontConfig, raw.get("font", {})),
            overlay=cls._merge_dataclass(OverlayConfig, raw.get("overlay", {})),
            lyrics=cls._merge_dataclass(LyricsConfig, raw.get("lyrics", {})),
            cache=cls._merge_dataclass(CacheConfig, raw.get("cache", {})),
            network=cls._merge_dataclass(NetworkConfig, raw.get("network", {})),
            clock=cls._merge_dataclass(ClockConfig, raw.get("clock", {})),
        )
        config.overlay.layout_preset = normalize_layout_preset(config.overlay.layout_preset)
        config.overlay.context_animation_style = normalize_context_animation_style(
            getattr(config.overlay, "context_animation_style", "slide")
        )
        return config

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def get_preset_font_color(self, layout_preset: str | None) -> str:
        preset = normalize_layout_preset(layout_preset)
        raw = self.font.preset_colors.get(preset)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return str(self.font.color)

    def set_preset_font_color(self, layout_preset: str | None, color: str) -> None:
        preset = normalize_layout_preset(layout_preset)
        value = str(color or "").strip()
        if not value:
            return
        self.font.preset_colors[preset] = value

    def get_preset_always_on_top(self, layout_preset: str | None) -> bool:
        preset = normalize_layout_preset(layout_preset)
        raw = self.overlay.always_on_top_by_preset.get(preset)
        if isinstance(raw, bool):
            return raw
        return bool(self.overlay.always_on_top)

    def set_preset_always_on_top(self, layout_preset: str | None, enabled: bool) -> None:
        preset = normalize_layout_preset(layout_preset)
        self.overlay.always_on_top_by_preset[preset] = bool(enabled)

    def position_key(
        self,
        screen_name: str,
        scale_percent: int,
        screen_width: int,
        screen_height: int,
        layout_preset: str | None = None,
    ) -> str:
        base = f"{screen_name}|{scale_percent}|{screen_width}x{screen_height}"
        preset = (layout_preset or "").strip().lower()
        if not preset:
            return base
        return f"{base}|{preset}"

    def get_saved_position(
        self,
        screen_name: str,
        scale_percent: int,
        screen_width: int,
        screen_height: int,
        layout_preset: str | None = None,
    ) -> tuple[int, int] | None:
        pos = None
        if layout_preset:
            preset_key = self.position_key(
                screen_name,
                scale_percent,
                screen_width,
                screen_height,
                layout_preset=layout_preset,
            )
            pos = self.overlay.positions.get(preset_key)
        if not pos:
            # Backward-compatible fallback for configs saved before per-preset positions.
            legacy_key = self.position_key(screen_name, scale_percent, screen_width, screen_height)
            pos = self.overlay.positions.get(legacy_key)
        if not pos:
            return None
        if "x" not in pos or "y" not in pos:
            return None
        return int(pos["x"]), int(pos["y"])

    def set_saved_position(
        self,
        screen_name: str,
        scale_percent: int,
        screen_width: int,
        screen_height: int,
        x: int,
        y: int,
        layout_preset: str | None = None,
    ) -> None:
        key = self.position_key(
            screen_name,
            scale_percent,
            screen_width,
            screen_height,
            layout_preset=layout_preset,
        )
        self.overlay.positions[key] = {"x": int(x), "y": int(y)}


def default_config() -> AppConfig:
    return AppConfig()


def load_config(paths: AppPaths) -> AppConfig:
    paths.ensure()
    if not paths.config_file.exists():
        cfg = default_config()
        save_config(paths, cfg)
        return cfg

    try:
        raw = json.loads(paths.config_file.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("config root must be an object")
        cfg = AppConfig.from_dict(raw)
        cache_raw = raw.get("cache", {}) if isinstance(raw.get("cache", {}), dict) else {}
        if cache_raw.get("max_entries") == 100:
            cfg.cache.max_entries = 500
            save_config(paths, cfg)
        return cfg
    except Exception:
        cfg = default_config()
        save_config(paths, cfg)
        return cfg


def save_config(paths: AppPaths, config: AppConfig) -> None:
    paths.ensure()
    tmp_path = paths.config_file.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(paths.config_file)


def write_default_config_snapshot(snapshot_path: Path | None = None) -> Path:
    target = snapshot_path or (Path(__file__).resolve().parent / "config.default.json")
    target.write_text(
        json.dumps(default_config().to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target
