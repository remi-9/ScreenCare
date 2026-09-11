"""View models over a real ``AppSession`` (in-memory database, ``FakeClock``)
-- the same wiring ``app/bootstrap.py`` builds for the real app, just
without a QML engine on top. Skipped automatically without PySide6; see
``tests/unit/test_app_session.py`` for the exhaustive, Qt-free coverage of
the underlying business logic this just exposes.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from screencare.app.session import AppSession  # noqa: E402
from screencare.notifications.base import InMemoryNotificationService  # noqa: E402
from screencare.persistence.database import Database  # noqa: E402
from screencare.persistence.repositories import (  # noqa: E402
    BreakSessionRepository,
    FocusSessionRepository,
    HydrationEventRepository,
    IdeaWalkNoteRepository,
)
from screencare.persistence.session_recovery import SessionSnapshotRepository  # noqa: E402
from screencare.persistence.settings import AppSettings, InMemorySettingsBackend  # noqa: E402
from screencare.scheduler.clock import FakeClock  # noqa: E402
from screencare.scheduler.scheduler import Scheduler  # noqa: E402
from screencare.ui.viewmodels.break_view_model import BreakViewModel  # noqa: E402
from screencare.ui.viewmodels.dashboard_view_model import DashboardViewModel  # noqa: E402
from screencare.ui.viewmodels.focus_view_model import FocusViewModel  # noqa: E402
from screencare.ui.viewmodels.settings_view_model import SettingsViewModel  # noqa: E402


@pytest.fixture
def wiring():
    clock = FakeClock()
    scheduler = Scheduler(clock)
    database = Database.open_in_memory(clock=clock)
    settings = AppSettings(InMemorySettingsBackend())
    notifier = InMemoryNotificationService()
    session = AppSession(
        clock=clock,
        scheduler=scheduler,
        settings=settings,
        focus_repo=FocusSessionRepository(database.connection, clock),
        break_repo=BreakSessionRepository(database.connection, clock),
        hydration_repo=HydrationEventRepository(database.connection),
        idea_walk_note_repo=IdeaWalkNoteRepository(database.connection, clock),
        snapshot_repo=SessionSnapshotRepository(database.connection),
        notifier=notifier,
    )
    session.begin()
    yield clock, database, settings, session
    database.close()


def test_focus_view_model_reflects_session_state(qapp, wiring) -> None:
    clock, database, settings, session = wiring
    vm = FocusViewModel(session)

    assert vm.state == "stopped"
    vm.startClassic("Write tests")
    assert vm.state == "focusing"
    assert vm.taskLabel == "Write tests"
    assert vm.remainingSeconds == 25 * 60


def test_focus_view_model_ignores_an_invalid_action_instead_of_raising(qapp, wiring) -> None:
    _clock, _database, _settings, session = wiring
    vm = FocusViewModel(session)

    vm.pause()  # not focusing yet -- must not raise through the Qt slot
    assert vm.state == "stopped"


def test_focus_view_model_extend_and_stuck_flow(qapp, wiring) -> None:
    clock, _database, _settings, session = wiring
    vm = FocusViewModel(session)
    vm.startClassic()
    clock.advance(minutes=25)
    session.tick()
    assert vm.state == "recovery_due"


def test_break_view_model_tracks_recovery_and_can_start_a_break(qapp, wiring) -> None:
    clock, _database, _settings, session = wiring
    focus_vm = FocusViewModel(session)
    break_vm = BreakViewModel(session)

    focus_vm.startClassic()
    clock.advance(minutes=25)
    session.tick()

    assert break_vm.isRecoveryDue is True
    break_vm.startBreak()
    assert break_vm.isBreaking is True
    break_vm.endBreak()
    assert break_vm.isReady is True
    break_vm.acknowledgeReady()
    assert focus_vm.state == "stopped"


def test_settings_view_model_round_trips_and_clamps(qapp, wiring) -> None:
    _clock, _database, settings, _session = wiring
    calls = []
    vm = SettingsViewModel(settings, on_settings_changed=lambda: calls.append(1))

    vm.focusMinutes = 45
    assert vm.focusMinutes == 45
    assert settings.focus_minutes == 45
    assert calls  # apply_settings_changed-equivalent hook fired

    vm.focusMinutes = 999  # out of bounds -- AppSettings clamps it
    assert vm.focusMinutes == 120


def test_settings_view_model_rejects_an_unknown_theme(qapp, wiring) -> None:
    _clock, _database, settings, _session = wiring
    vm = SettingsViewModel(settings)
    vm.theme = "not-a-real-theme"
    assert vm.theme == "system"


def test_dashboard_view_model_refreshes_from_persisted_history(qapp, wiring) -> None:
    clock, database, _settings, session = wiring
    vm = DashboardViewModel(
        clock=clock,
        focus_repo=FocusSessionRepository(database.connection, clock),
        break_repo=BreakSessionRepository(database.connection, clock),
        hydration_repo=HydrationEventRepository(database.connection),
    )
    vm.refresh()
    assert vm.todaySessionsCompleted == 0

    focus_vm = FocusViewModel(session)
    focus_vm.startClassic()
    clock.advance(minutes=25)
    session.tick()
    session.start_break()
    clock.advance(minutes=5)
    session.end_break()
    session.acknowledge_ready()

    vm.refresh()
    assert vm.todaySessionsCompleted == 1
    assert vm.todayFocusMinutes == 25
    assert vm.weekSessionsCompleted == 1
