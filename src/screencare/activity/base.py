"""OS-agnostic interfaces for activity monitoring, power events, and
autostart -- the only way platform-specific code may reach engine or
application logic (``ScreenCare — Implementation Standards.md`` section 13:
"Hide all platform-specific functionality behind clean interfaces.").

Every protocol here is intentionally narrow: idle duration, locked state,
sleep/wake notification, and a simple autostart toggle -- nothing that
could be mistaken for keystroke, screenshot, or clipboard capture
(``ScreenCare — Technical.md`` section 28, Implementation Standards.md
section 15: no keyboard/mouse hooks, ever).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class ActivityProvider(Protocol):
    """Answers "how long has the user been idle" and "is the session
    locked" -- nothing else."""

    def idle_seconds(self) -> float:
        """Seconds since the last user input, system-wide."""
        ...

    def is_locked(self) -> bool:
        """Whether the current session is locked (the login/lock screen is
        showing)."""
        ...


@runtime_checkable
class PowerMonitor(Protocol):
    """Notifies about system sleep/wake. Deliberately separate from
    lock/unlock -- a laptop can be locked without sleeping, and vice
    versa (``ScreenCare — Technical.md`` section 13)."""

    def start(self, *, on_sleep: Callable[[], None], on_wake: Callable[[], None]) -> None:
        """Begin listening. ``on_sleep``/``on_wake`` are called on
        whatever thread the platform delivers the event on -- the Windows
        adapter delivers both on the Qt main thread (via a native event
        filter riding Qt's own message loop), so callbacks may safely call
        straight into :class:`~screencare.app.session.AppSession`."""
        ...

    def stop(self) -> None:
        """Stop listening. Safe to call even if :meth:`start` was never
        called."""
        ...


@runtime_checkable
class AutostartService(Protocol):
    """Registers/unregisters ScreenCare to launch at login. Implementations
    must never require elevated privileges or install a service
    (Implementation Standards.md section 15)."""

    def is_enabled(self) -> bool: ...

    def set_enabled(self, enabled: bool) -> None: ...


@dataclass(frozen=True)
class PlatformCapabilities:
    """What this platform/session can actually do, detected once at
    startup so an unsupported optional feature degrades gracefully instead
    of crashing (``ScreenCare — Technical.md`` section 31,
    Implementation Standards.md section 14). Every field defaults to
    unsupported -- a platform with no adapter at all (macOS/Linux, for
    now) is fully described by ``PlatformCapabilities()``."""

    idle_detection: bool = False
    lock_detection: bool = False
    sleep_detection: bool = False
    native_notifications: bool = False
    tray_available: bool = False
    autostart: bool = False
    fullscreen_detection: bool = False
