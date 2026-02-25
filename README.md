# STZLyrics Overlay (Python)

STZLyrics Overlay is a Windows 10/11 synced-lyrics overlay inspired by an existing Rainmeter workflow (`STZLyrics.ini`, `Lyrics.lua`, `Settings.ini`), reimplemented in Python.

It uses GSMTC (Windows Global System Media Transport Controls) to read the current media session and LRCLib to fetch lyrics when available.

## Features

- Frameless transparent overlay window
- Click-through support (`WS_EX_TRANSPARENT`)
- Optional snap to screen edge/taskbar
- Always-on-top support (including taskbar interaction handling on Windows)
- Configurable font, color, shadow, offset, and language
- GUI settings window (localized)
- Tray icon controls (show/hide, toggles, reload, cache folder, exit)
- GSMTC polling (Spotify prioritized when applicable)
- LRC parsing + incremental lyric synchronization
- Local smoothing clock to reduce GSMTC jitter impact on UI/lyrics
- Local LRU lyrics cache with persistent `index.json`
- `Context (2+2)` preset (previous/current/next lyric lines)
- Configurable context transition animation (`Slide`, `Slide + Fade`, `Fade`, `None`)
- Per-preset preferences for:
  - position
  - lyric color
  - always-on-top
- Optional "Start with Windows" (via `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`)

## Project Structure

```text
app/
  main.py
  controller.py
  config.py
  logging_utils.py
  config.default.json
  i18n.py
  services/
    media_session.py
    lrclib_client.py
    lyrics_sync.py
    cache.py
    windows_startup.py
  ui/
    overlay_window.py
    settings_window.py
    system_tray.py
    windows_api.py
tests/
  test_lrc_parser.py
```

## Requirements

- Windows 10/11
- Python 3.10+
- A player compatible with Windows Media Session / GSMTC (Spotify usually works well)

## Installation (Dev)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -U pip
pip install -e .
```

## Run

```powershell
python -m app.main
```

Or, after `pip install -e .`:

```powershell
stzlyrics-overlay
```

## Configuration

The app stores configuration in:

- `%APPDATA%\STZLyricsOverlay\config.json`

Generated folders:

- `%APPDATA%\STZLyricsOverlay\cache\` (`.lrc` / `.txt` files + `index.json`)
- `%APPDATA%\STZLyricsOverlay\logs\`

Reference default config in the repository:

- `app/config.default.json`

Main configuration areas:

- `font.*` (family, size, color, shadow)
- `font.preset_colors` (lyric color per preset)
- `lyrics.offset_seconds`
- `lyrics.update_interval_ms`
- `lyrics.language`
- `cache.max_entries`
- `overlay.click_through`
- `overlay.snap_to_taskbar`
- `overlay.layout_preset`
- `overlay.context_animation_style`
- `overlay.start_with_windows`
- `overlay.always_on_top_by_preset`
- `overlay.positions` (saved automatically per monitor/DPI/preset)

## Tray (Quick Actions)

- Show/Hide overlay
- Toggle click-through
- Toggle snap
- Reload lyrics
- Open cache folder
- Reload config
- Exit

## Tests (Parser / Sync)

```powershell
pytest
```

## Notes / Limitations

- Correct line-by-line sync depends on lyric availability for the current track, especially synced LRC lyrics.
- Not every song has lyrics available, and not every available lyric is synced (LRC).
- When only unsynced lyrics are available (or none are found), the overlay falls back to a friendly message.
- GSMTC session selection (and timeline quality) may vary depending on the media player.
- Some players (notably Spotify in some cases) can report timeline position with jitter/freezes; the app mitigates this, but source behavior can still affect precision.

## Releases

You can run this project from source during development, but the intended end-user distribution is a Windows `.exe` build (e.g. PyInstaller) and an installer package (e.g. Inno Setup).

## ⚖️ Licensing (Dual Licensing)

STZLyrics Overlay is available under two distinct licenses:

1. Community Use (GPLv3): Free for personal use and open-source projects. You are free to modify and distribute this project, provided that your changes remain open-source.
2. Commercial Use: For companies wishing to integrate this overlay, synchronization logic, or related UI/UX behavior into proprietary software, OEM desktop themes, or commercial kiosk interfaces.

To acquire a commercial license, please contact: [starzynhobr@gmail.com](mailto:starzynhobr@gmail.com)