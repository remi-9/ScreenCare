"""Windows implementation of :class:`~screencare.activity.base.ActivityProvider`,
:class:`~screencare.activity.base.PowerMonitor`, and
:class:`~screencare.activity.base.AutostartService`.

Uses only the APIs ``ScreenCare — Technical.md`` sections 13/32 name --
``GetLastInputInfo`` for idle duration, ``WTSRegisterSessionNotification``
+ ``WM_WTSSESSION_CHANGE`` for lock/unlock, ``WM_POWERBROADCAST`` for
sleep/wake -- through ``ctypes``, never a keyboard/mouse hook and never an
elevated privilege (Implementation Standards.md section 15). Constants
verified against current Microsoft Learn documentation rather than
guessed:

- https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-getlastinputinfo
- https://learn.microsoft.com/windows/win32/api/wtsapi32/nf-wtsapi32-wtsregistersessionnotification
- https://learn.microsoft.com/windows/win32/termserv/wm-wtssession-change
  (WM_WTSSESSION_CHANGE = 0x02B1)
- https://learn.microsoft.com/windows/win32/power/wm-powerbroadcast

This module imports ``winreg`` and ``ctypes.windll`` at need, both of which
only exist on Windows -- it must only ever be imported behind a
``sys.platform == "win32"`` check (``platform/factory.py`` is the only
caller), keeping that check concentrated in one place
(Implementation Standards.md section 13). It cannot be imported or
exercised outside a real Windows machine, so none of it is covered by the
cross-platform test suite; verify it manually there.
"""

from __future__ import annotations

import contextlib
import ctypes
import logging
import sys
import winreg
from collections.abc import Callable
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication

logger = logging.getLogger(__name__)

_WM_WTSSESSION_CHANGE = 0x02B1
_WTS_SESSION_LOCK = 0x7
_WTS_SESSION_UNLOCK = 0x8
_NOTIFY_FOR_THIS_SESSION = 0

_WM_POWERBROADCAST = 0x0218
_PBT_APMSUSPEND = 0x4
_PBT_APMRESUMEAUTOMATIC = 0x12
_PBT_APMRESUMESUSPEND = 0x7

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE_NAME = "ScreenCare"


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


class WindowsActivityProvider:
    """``idle_seconds()`` via ``GetLastInputInfo``; ``is_locked()`` reads a
    flag toggled by :class:`WindowsSessionMonitor`'s native event filter --
    there is no polling API for lock state, only the
    ``WM_WTSSESSION_CHANGE`` notification (Technical.md section 13)."""

    def __init__(self) -> None:
        self._locked = False

    def idle_seconds(self) -> float:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            raise OSError("GetLastInputInfo failed")
        tick_count = ctypes.windll.kernel32.GetTickCount64()
        return max(0.0, (tick_count - info.dwTime) / 1000.0)

    def is_locked(self) -> bool:
        return self._locked

    def set_locked(self, locked: bool) -> None:
        """Called by :class:`WindowsSessionMonitor` when a
        ``WM_WTSSESSION_CHANGE`` message arrives."""
        self._locked = locked


class WindowsSessionMonitor(QAbstractNativeEventFilter):
    """Registers a Qt top-level window for Windows session-change and
    power-broadcast notifications, and installs a native event filter on
    the running ``QApplication`` to observe them. Both arrive on the Qt
    main thread, riding Qt's own message loop -- no extra thread needed
    (Implementation Standards.md section 12: "Do not introduce background
    threads without need."). Implements the
    :class:`~screencare.activity.base.PowerMonitor` protocol for sleep/wake;
    lock/unlock instead just update ``activity_provider`` and are picked up
    on ``AppSession``'s next poll, since lock timing is not as
    time-critical as "don't count sleep as focus time"."""

    def __init__(self, window, activity_provider: WindowsActivityProvider) -> None:
        super().__init__()
        self._window = window
        self._activity_provider = activity_provider
        self._on_sleep: Callable[[], None] = lambda: None
        self._on_wake: Callable[[], None] = lambda: None
        self._registered = False

    def start(self, *, on_sleep: Callable[[], None], on_wake: Callable[[], None]) -> None:
        self._on_sleep = on_sleep
        self._on_wake = on_wake
        hwnd = int(self._window.winId())
        if not ctypes.windll.wtsapi32.WTSRegisterSessionNotification(
            hwnd, _NOTIFY_FOR_THIS_SESSION
        ):
            logger.warning("WTSRegisterSessionNotification failed; lock detection disabled")
        app = QCoreApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self)
        self._registered = True

    def stop(self) -> None:
        if not self._registered:
            return
        app = QCoreApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self)
        hwnd = int(self._window.winId())
        if not ctypes.windll.wtsapi32.WTSUnRegisterSessionNotification(hwnd):
            logger.warning("WTSUnRegisterSessionNotification failed")
        self._registered = False

    def nativeEventFilter(self, event_type, message):  # noqa: N802 (Qt override)
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == _WM_WTSSESSION_CHANGE:
            if msg.wParam == _WTS_SESSION_LOCK:
                self._activity_provider.set_locked(True)
            elif msg.wParam == _WTS_SESSION_UNLOCK:
                self._activity_provider.set_locked(False)
        elif msg.message == _WM_POWERBROADCAST:
            if msg.wParam == _PBT_APMSUSPEND:
                self._on_sleep()
            elif msg.wParam in (_PBT_APMRESUMEAUTOMATIC, _PBT_APMRESUMESUSPEND):
                self._on_wake()
        return False, 0


class WindowsAutostartService:
    """Adds/removes a per-user ``Run`` registry value -- no admin rights,
    no Windows service (Implementation Standards.md section 15: "Do not
    install Windows services for the MVP. Do not use elevated
    privileges.")."""

    def __init__(self, *, value_name: str = _RUN_VALUE_NAME) -> None:
        self._value_name = value_name

    def _command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'
        return f'"{sys.executable}" -m screencare'

    def is_enabled(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, self._value_name)
            return True
        except OSError:
            return False

    def set_enabled(self, enabled: bool) -> None:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, self._value_name, 0, winreg.REG_SZ, self._command())
                return
            with contextlib.suppress(FileNotFoundError):
                winreg.DeleteValue(key, self._value_name)
