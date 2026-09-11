"""Concentrates every ``sys.platform`` branch in one place
(``ScreenCare — Implementation Standards.md`` section 13: "Core logic must
not contain ``if sys.platform`` spread throughout the codebase. Keep those
checks concentrated in bootstrap/factory code."). Called once from
``app/bootstrap.py`` after the QML root window exists -- the Windows
adapter needs a native window handle to register for session
notifications.

Any adapter that fails to construct is dropped rather than raised: an
unavailable optional integration must never crash the app
(``ScreenCare — Technical.md`` section 41).
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

from screencare.activity.base import (
    ActivityProvider,
    AutostartService,
    PlatformCapabilities,
    PowerMonitor,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlatformAdapters:
    activity_provider: ActivityProvider | None
    power_monitor: PowerMonitor | None
    autostart_service: AutostartService | None
    capabilities: PlatformCapabilities


_NONE_ADAPTERS = PlatformAdapters(
    activity_provider=None,
    power_monitor=None,
    autostart_service=None,
    capabilities=PlatformCapabilities(),
)


def build_platform_adapters(window: object | None) -> PlatformAdapters:
    """``window`` is the QML engine's root window (used only on Windows,
    to register for session-change notifications) -- ``None`` is fine and
    simply disables lock/sleep detection while leaving idle detection and
    autostart available."""
    if sys.platform == "win32":
        return _build_windows_adapters(window)
    logger.info(
        "No platform adapter for %s yet; idle/lock/sleep detection and autostart disabled",
        sys.platform,
    )
    return _NONE_ADAPTERS


def _build_windows_adapters(window: object | None) -> PlatformAdapters:
    try:
        from screencare.platform.windows import (
            WindowsActivityProvider,
            WindowsAutostartService,
            WindowsSessionMonitor,
        )
    except ImportError:
        logger.exception("Windows platform adapter module failed to import")
        return _NONE_ADAPTERS

    activity_provider: ActivityProvider | None = None
    power_monitor: PowerMonitor | None = None
    autostart_service: AutostartService | None = None

    try:
        windows_activity = WindowsActivityProvider()
        activity_provider = windows_activity
        if window is not None:
            power_monitor = WindowsSessionMonitor(window, windows_activity)
    except OSError:
        logger.exception("Failed to initialize Windows activity/session monitoring")

    try:
        autostart_service = WindowsAutostartService()
    except OSError:
        logger.exception("Failed to initialize Windows autostart service")

    return PlatformAdapters(
        activity_provider=activity_provider,
        power_monitor=power_monitor,
        autostart_service=autostart_service,
        capabilities=PlatformCapabilities(
            idle_detection=activity_provider is not None,
            lock_detection=activity_provider is not None,
            sleep_detection=power_monitor is not None,
            native_notifications=False,
            tray_available=False,  # bootstrap.py knows the real tray state; left False here
            autostart=autostart_service is not None,
            fullscreen_detection=False,
        ),
    )
