"""Concrete OS adapters (idle, lock, sleep-wake, autostart) behind the
``screencare.activity`` interfaces, plus ``factory.py``'s
``build_platform_adapters()`` -- the one place that branches on
``sys.platform``.

Windows (``windows.py``) is the first fully implemented and tested
platform, as of Phase 5. macOS and Linux adapters follow the same
interfaces later without changing core logic.
"""
