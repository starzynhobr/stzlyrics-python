from __future__ import annotations

import ctypes
import sys


MUTEX_NAME = "Local\\STZLabs.STZLyricsOverlay.SingleInstance"
ERROR_ALREADY_EXISTS = 183


class SingleInstanceGuard:
    def __init__(self, handle: int, close_handle) -> None:
        self._handle = handle
        self._close_handle = close_handle

    def close(self) -> None:
        if self._handle:
            self._close_handle(self._handle)
            self._handle = 0


def acquire_single_instance(name: str = MUTEX_NAME) -> SingleInstanceGuard | None:
    """Hold a Windows mutex until close(); return None when another instance owns it."""
    if sys.platform != "win32":
        raise OSError("STZLyrics Overlay requires Windows")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_mutex = kernel32.CreateMutexW
    create_mutex.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    create_mutex.restype = ctypes.c_void_p
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [ctypes.c_void_p]
    close_handle.restype = ctypes.c_bool

    ctypes.set_last_error(0)
    handle = create_mutex(None, False, name)
    last_error = ctypes.get_last_error()
    if not handle:
        raise ctypes.WinError(last_error)
    if last_error == ERROR_ALREADY_EXISTS:
        close_handle(handle)
        return None
    return SingleInstanceGuard(handle, close_handle)
