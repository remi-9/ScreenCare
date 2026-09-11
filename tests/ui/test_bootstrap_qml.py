"""Smoke test: does the application's real QML shell actually load, wired
to real view models over a real (temporary) database?

Skipped automatically if PySide6 is not installed (``pytest.importorskip``)
so the suite stays runnable everywhere, but runs for real wherever PySide6
is present -- the developer's machine, CI, and packaged-build smoke tests.
This is the acceptance check from ``ScreenCare — Implementation Standards.md``
section 49 ("app starts" / "QML loads") and ``ScreenCare — Technical.md``
section 40's UI test list ("QML loads", "main view opens", "settings
bindings work"), now covering the real Phase 4 shell rather than the Phase 1
placeholder window.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from screencare.app.bootstrap import (  # noqa: E402
    MAIN_QML,
    build_app_session,
    create_engine,
)
from screencare.notifications.base import InMemoryNotificationService  # noqa: E402
from screencare.persistence.database import Database  # noqa: E402
from screencare.persistence.repositories import (  # noqa: E402
    BreakSessionRepository,
    FocusSessionRepository,
    HydrationEventRepository,
)
from screencare.persistence.settings import AppSettings, InMemorySettingsBackend  # noqa: E402
from screencare.scheduler.clock import FakeClock  # noqa: E402
from screencare.ui.viewmodels.break_view_model import BreakViewModel  # noqa: E402
from screencare.ui.viewmodels.dashboard_view_model import DashboardViewModel  # noqa: E402
from screencare.ui.viewmodels.focus_view_model import FocusViewModel  # noqa: E402
from screencare.ui.viewmodels.settings_view_model import SettingsViewModel  # noqa: E402


def test_main_qml_file_exists() -> None:
    assert MAIN_QML.is_file()


@pytest.fixture
def wired_engine(qapp):
    clock = FakeClock()
    database = Database.open_in_memory(clock=clock)
    settings = AppSettings(InMemorySettingsBackend())
    notifier = InMemoryNotificationService()

    app_session = build_app_session(
        database=database, settings=settings, notifier=notifier, clock=clock
    )
    app_session.reconcile_startup()
    app_session.begin()

    focus_vm = FocusViewModel(app_session)
    break_vm = BreakViewModel(app_session)
    settings_vm = SettingsViewModel(
        settings, on_settings_changed=app_session.apply_settings_changed
    )
    dashboard_vm = DashboardViewModel(
        clock=clock,
        focus_repo=FocusSessionRepository(database.connection, clock),
        break_repo=BreakSessionRepository(database.connection, clock),
        hydration_repo=HydrationEventRepository(database.connection),
    )

    engine = create_engine(
        qapp,
        app_session=app_session,
        focus_vm=focus_vm,
        break_vm=break_vm,
        settings_vm=settings_vm,
        dashboard_vm=dashboard_vm,
        tray_available=False,
    )
    yield engine
    engine.deleteLater()
    database.close()


def test_bootstrap_loads_root_qml_wired_to_real_view_models(wired_engine) -> None:
    assert wired_engine.rootObjects(), "Main.qml failed to load"
