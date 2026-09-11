"""Shared test configuration.

Forces the Qt "offscreen" platform plugin so UI tests can run in CI or any
headless environment without a real display. This must be set before
PySide6 constructs any ``QGuiApplication``, hence a session-scoped
``conftest.py`` rather than doing it inside a fixture.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
