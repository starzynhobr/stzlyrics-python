from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "STZLyricsOverlay"

try:  # pragma: no cover - platform-specific import
    import winreg
except Exception:  # pragma: no cover
    winreg = None  # type: ignore[assignment]


def is_supported() -> bool:
    return bool(sys.platform.startswith("win") and winreg is not None)


def _prefer_pythonw(executable: str) -> str:
    exe_path = Path(executable)
    if exe_path.name.lower() != "python.exe":
        return str(exe_path)
    candidate = exe_path.with_name("pythonw.exe")
    if candidate.exists():
        return str(candidate)
    return str(exe_path)


def build_startup_command() -> str:
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([os.path.abspath(sys.executable)])
    python_exe = _prefer_pythonw(os.path.abspath(sys.executable))
    return subprocess.list2cmdline([python_exe, "-m", "app.main"])


def get_startup_command() -> str | None:
    if not is_supported():
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:  # type: ignore[union-attr]
            value, _ = winreg.QueryValueEx(key, RUN_VALUE_NAME)  # type: ignore[union-attr]
            text = str(value or "").strip()
            return text or None
    except FileNotFoundError:
        return None
    except OSError:
        return None


def is_startup_enabled() -> bool:
    return get_startup_command() is not None


def set_startup_enabled(enabled: bool) -> bool:
    if not is_supported():
        return False
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:  # type: ignore[union-attr]
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, build_startup_command())  # type: ignore[union-attr]
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE_NAME)  # type: ignore[union-attr]
                except FileNotFoundError:
                    pass
    except OSError:
        return False
    return is_startup_enabled() if enabled else (not is_startup_enabled())
