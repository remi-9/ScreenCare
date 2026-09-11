"""Smoke test: does the application's root QML actually load?

Skipped automatically if PySide6 is not installed in the current
environment (``pytest.importorskip``) so the suite stays runnable
everywhere, but runs for real wherever PySide6 is present — the developer's
machine, CI, and packaged-build smoke tests. This is the Phase 1 acceptance
check from ``ScreenCare — Implementation Standards.md`` section 49
("app starts" / "QML loads") and must keep passing before later phases add
real business logic behind this window.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from screencare.app.bootstrap import MAIN_QML  # noqa: E402


def test_main_qml_file_exists() -> None:
    assert MAIN_QML.is_file()


def test_bootstrap_loads_root_qml(qtbot) -> None:
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine

    engine = QQmlApplicationEngine()
    engine.load(QUrl.fromLocalFile(str(MAIN_QML)))

    assert engine.rootObjects(), "Main.qml failed to load"
