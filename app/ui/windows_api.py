from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass

IS_WINDOWS = sys.platform.startswith("win")

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

ABM_GETTASKBARPOS = 0x00000005


@dataclass(slots=True)
class WinRect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


if IS_WINDOWS:  # pragma: no cover - platform-specific
    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    class APPBARDATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd", wintypes.HWND),
            ("uCallbackMessage", wintypes.UINT),
            ("uEdge", wintypes.UINT),
            ("rc", RECT),
            ("lParam", ctypes.c_int),
        ]


def set_click_through(hwnd: int, enabled: bool) -> None:
    if not IS_WINDOWS or not hwnd:
        return
    try:
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex_style |= WS_EX_LAYERED
        if enabled:
            ex_style |= WS_EX_TRANSPARENT
        else:
            ex_style &= ~WS_EX_TRANSPARENT
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
    except Exception:
        return


def set_window_topmost(hwnd: int, enabled: bool, *, force_reorder: bool = False) -> None:
    if not IS_WINDOWS or not hwnd:
        return
    try:
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
        if enabled and force_reorder:
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
            return
        insert_after = HWND_TOPMOST if enabled else HWND_NOTOPMOST
        user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, flags)
    except Exception:
        return


def get_taskbar_rect() -> WinRect | None:
    if not IS_WINDOWS:  # pragma: no cover
        return None
    try:
        abd = APPBARDATA()
        abd.cbSize = ctypes.sizeof(APPBARDATA)
        ok = shell32.SHAppBarMessage(ABM_GETTASKBARPOS, ctypes.byref(abd))
        if not ok:
            return None
        return WinRect(abd.rc.left, abd.rc.top, abd.rc.right, abd.rc.bottom)
    except Exception:
        return None


def snap_position(
    x: int,
    y: int,
    width: int,
    height: int,
    screen_rect: WinRect,
    threshold: int,
    prefer_taskbar: bool = True,
) -> tuple[int, int]:
    threshold = max(0, int(threshold))
    new_x, new_y = int(x), int(y)

    if abs(new_x - screen_rect.left) <= threshold:
        new_x = screen_rect.left
    if abs((new_x + width) - screen_rect.right) <= threshold:
        new_x = screen_rect.right - width
    if abs(new_y - screen_rect.top) <= threshold:
        new_y = screen_rect.top
    if abs((new_y + height) - screen_rect.bottom) <= threshold:
        new_y = screen_rect.bottom - height

    if prefer_taskbar:
        taskbar = get_taskbar_rect()
        if taskbar:
            if taskbar.width >= taskbar.height:
                target_y = taskbar.top - height
                if abs(new_y - target_y) <= threshold:
                    new_y = target_y
            else:
                # Left or right vertical taskbar.
                if taskbar.left <= screen_rect.left + threshold:
                    target_x = taskbar.right
                    if abs(new_x - target_x) <= threshold:
                        new_x = target_x
                else:
                    target_x = taskbar.left - width
                    if abs(new_x - target_x) <= threshold:
                        new_x = target_x

    return new_x, new_y
