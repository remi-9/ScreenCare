"""``build_platform_adapters`` -- only the non-Windows fallback branch is
exercised here (this sandbox runs Linux); the Windows branch imports
``winreg``/``ctypes.windll``, which only exist on real Windows, so
``screencare.platform.windows`` is never imported in this suite. See
``ARCHITECTURE.md`` for how that's verified instead (manually, on the
user's machine).
"""

from __future__ import annotations

from unittest.mock import patch

from screencare.platform.factory import build_platform_adapters


def test_non_windows_platform_returns_no_adapters() -> None:
    with patch("screencare.platform.factory.sys") as fake_sys:
        fake_sys.platform = "linux"
        adapters = build_platform_adapters(window=None)

    assert adapters.activity_provider is None
    assert adapters.power_monitor is None
    assert adapters.autostart_service is None
    assert adapters.capabilities.idle_detection is False
    assert adapters.capabilities.lock_detection is False
    assert adapters.capabilities.sleep_detection is False
    assert adapters.capabilities.autostart is False
