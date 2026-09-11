"""End-to-end tests of the application layer, entirely without Qt: a real
(in-memory) SQLite database, a real ``Scheduler``, and a ``FakeClock`` so
every timing scenario is deterministic. This is what lets Phase 4's core
wiring — session lifecycle, notification merging, crash-recovery
checkpointing — be fully verified in an environment where PySide6 can't be
installed; only the thin Qt view-model/tray layer on top of ``AppSession``
needs a human (or CI with PySide6) to confirm.
"""

from __future__ import annotations

import pytest

from screencare.app.session import CHECKPOINT_MIN_INTERVAL_SECONDS, AppSession
from screencare.domain.enums import FocusFeedback, FocusMode, FocusState
from screencare.notifications.base import InMemoryNotificationService
from screencare.persistence.database import Database
from screencare.persistence.repositories import (
    BreakSessionRepository,
    FocusSessionRepository,
    HydrationEventRepository,
    IdeaWalkNoteRepository,
)
from screencare.persistence.session_recovery import RecoveryAction, SessionSnapshotRepository
from screencare.persistence.settings import AppSettings, InMemorySettingsBackend
from screencare.scheduler.clock import FakeClock
from screencare.scheduler.scheduler import Scheduler


class _Harness:
    def __init__(self, configure_settings=None) -> None:
        self.clock = FakeClock()
        self.scheduler = Scheduler(self.clock)
        self.db = Database.open_in_memory(clock=self.clock)
        self.settings = AppSettings(InMemorySettingsBackend())
        # Settings a test cares about (e.g. Adaptive's focus_minutes, which
        # AdaptiveFocusEngine only ever reads once, at construction) must be
        # in place *before* AppSession is built -- matching the real app,
        # where settings are loaded before anything is constructed.
        if configure_settings is not None:
            configure_settings(self.settings)
        self.notifier = InMemoryNotificationService()
        self.changed_count = 0
        self.session = AppSession(
            clock=self.clock,
            scheduler=self.scheduler,
            settings=self.settings,
            focus_repo=FocusSessionRepository(self.db.connection, self.clock),
            break_repo=BreakSessionRepository(self.db.connection, self.clock),
            hydration_repo=HydrationEventRepository(self.db.connection),
            idea_walk_note_repo=IdeaWalkNoteRepository(self.db.connection, self.clock),
            snapshot_repo=SessionSnapshotRepository(self.db.connection),
            notifier=self.notifier,
            on_changed=self._on_changed,
        )

    def _on_changed(self) -> None:
        self.changed_count += 1

    def close(self) -> None:
        self.db.close()


@pytest.fixture
def h() -> _Harness:
    harness = _Harness()
    yield harness
    harness.close()


@pytest.fixture
def make_harness():
    harnesses: list[_Harness] = []

    def _make(configure_settings=None) -> _Harness:
        harness = _Harness(configure_settings)
        harnesses.append(harness)
        return harness

    yield _make
    for harness in harnesses:
        harness.close()


# -- startup reconciliation -------------------------------------------------


def test_reconcile_startup_with_nothing_persisted_is_a_no_op(h: _Harness) -> None:
    result = h.session.reconcile_startup()
    assert result.action is RecoveryAction.NONE
    assert result.snapshot is None


# -- basic lifecycle wiring ---------------------------------------------------


def test_start_focus_classic_uses_classic_durations(h: _Harness) -> None:
    h.session.begin()
    h.session.start_focus(FocusMode.CLASSIC, task_label="Write tests")
    assert h.session.focus_state is FocusState.FOCUSING
    assert h.session.remaining_seconds == 25 * 60
    assert h.session.task_label == "Write tests"


def test_pause_and_resume_preserve_remaining_time(h: _Harness) -> None:
    h.session.begin()
    h.session.start_focus(FocusMode.CLASSIC)
    h.clock.advance(minutes=10)
    h.session.pause()
    assert h.session.focus_state is FocusState.PAUSED

    h.clock.advance(hours=1)
    h.session.resume()
    h.clock.advance(minutes=15)
    h.scheduler.tick()
    assert h.session.focus_state is FocusState.RECOVERY_DUE


def test_full_session_persists_a_completed_summary(h: _Harness) -> None:
    h.session.begin()
    h.session.start_focus(FocusMode.CLASSIC, task_label="Write tests")
    h.clock.advance(minutes=25)
    h.scheduler.tick()
    assert h.session.focus_state is FocusState.RECOVERY_DUE

    h.session.start_break()
    h.clock.advance(minutes=5)
    summary = h.session.end_break(feedback=FocusFeedback.JUST_RIGHT)
    assert summary.outcome.value == "completed"
    assert summary.task_label == "Write tests"

    h.session.acknowledge_ready()
    assert h.session.focus_state is FocusState.STOPPED

    persisted = FocusSessionRepository(h.db.connection, h.clock).list_recent()
    assert len(persisted) == 1
    assert persisted[0].feedback is FocusFeedback.JUST_RIGHT

    breaks = BreakSessionRepository(h.db.connection, h.clock).list_recent()
    assert len(breaks) == 1


def test_stop_persists_an_abandoned_summary_and_clears_the_snapshot(h: _Harness) -> None:
    h.session.begin()
    h.session.start_focus(FocusMode.CLASSIC)
    h.clock.advance(minutes=5)
    summary = h.session.stop()
    assert summary is not None
    assert summary.outcome.value == "abandoned"

    assert SessionSnapshotRepository(h.db.connection).load() is None


# -- adaptive focus feedback --------------------------------------------------


def test_end_break_feedback_adjusts_the_next_adaptive_duration(h: _Harness) -> None:
    h.settings.focus_minutes = 25
    h.session.begin()
    h.session.start_focus(FocusMode.ADAPTIVE)
    assert h.session.remaining_seconds == 25 * 60

    h.clock.advance(minutes=25)
    h.scheduler.tick()
    h.session.start_break()
    h.clock.advance(minutes=5)
    # completion_rate = active/planned = 1.0 > 0.8, so TOO_SHORT bumps it up.
    h.session.end_break(feedback=FocusFeedback.TOO_SHORT)
    h.session.acknowledge_ready()

    assert h.session.adaptive_focus_seconds == 30 * 60
    h.session.start_focus(FocusMode.ADAPTIVE)
    assert h.session.remaining_seconds == 30 * 60


# -- notification merging (WellnessCoordinator wiring) ------------------------


def _configure_30min_hydration_35min_adaptive_focus(settings) -> None:
    settings.hydration_interval_minutes = 30  # the minimum allowed value
    settings.focus_minutes = 35  # AdaptiveFocusEngine's initial duration


def test_recovery_due_merges_a_hydration_reminder_that_fired_shortly_before(make_harness) -> None:
    # Hydration's minimum allowed interval is 30 minutes, so Adaptive mode
    # (its duration is settings-driven) is used to get a recovery break a
    # few minutes after that, well within the default 10-minute merge
    # window -- hydration is suppressed standalone (see
    # test_hydration_due_during_focus_defers_to_the_upcoming_recovery below)
    # and folded into the recovery break instead, exactly the worked example
    # in ScreenCare — Technical.md section 7.
    h = make_harness(_configure_30min_hydration_35min_adaptive_focus)
    h.session.begin()
    h.session.start_focus(FocusMode.ADAPTIVE)

    h.clock.advance(minutes=30)
    h.scheduler.tick()  # hydration due -> deferred, no standalone notification
    assert h.notifier.sent == []

    h.clock.advance(minutes=5)
    h.scheduler.tick()  # recovery due now, with hydration still pending from 5 min ago

    assert h.session.focus_state is FocusState.RECOVERY_DUE
    assert h.session.pending_recovery_includes_hydration is True
    last = h.notifier.last
    assert last is not None
    assert "water" in last.message.lower()


def test_recovery_due_without_nearby_hydration_does_not_mention_water(h: _Harness) -> None:
    h.settings.hydration_interval_minutes = 180  # far away
    h.session.apply_settings_changed()
    h.session.begin()
    h.session.start_focus(FocusMode.CLASSIC)

    h.clock.advance(minutes=25)
    h.scheduler.tick()

    assert h.session.pending_recovery_includes_hydration is False
    assert "water" not in h.notifier.last.message.lower()


def test_standalone_hydration_fires_when_no_session_is_active(h: _Harness) -> None:
    h.settings.hydration_interval_minutes = 30
    h.session.apply_settings_changed()
    h.session.begin()
    h.clock.advance(minutes=30)
    h.scheduler.tick()

    assert h.session.reminder_text == "Time to drink some water."
    assert any(n.id == "hydration_due" for n in h.notifier.sent)


def test_hydration_due_during_focus_defers_to_the_upcoming_recovery(make_harness) -> None:
    h = make_harness(_configure_30min_hydration_35min_adaptive_focus)
    h.settings.eye_reminder_enabled = False  # isolate this test to hydration timing only
    h.session.apply_settings_changed()
    h.session.begin()
    h.session.start_focus(FocusMode.ADAPTIVE)  # 35 min recovery, hydration due at 30 min

    h.clock.advance(minutes=30)
    # hydration due now; recovery is only 5 min away -> merge, don't fire standalone
    h.scheduler.tick()

    assert h.session.reminder_text == ""
    assert not any(n.id == "hydration_due" for n in h.notifier.sent)


def test_log_drink_persists_event_and_clears_the_reminder(h: _Harness) -> None:
    h.settings.hydration_interval_minutes = 30
    h.session.apply_settings_changed()
    h.session.begin()
    h.clock.advance(minutes=30)
    h.scheduler.tick()
    assert h.session.reminder_text != ""

    h.session.log_drink()
    assert h.session.reminder_text == ""
    events = HydrationEventRepository(h.db.connection).list_recent()
    assert len(events) == 1


# -- eye rest: quiet in-app banner, never an OS notification -----------------


def test_eye_rest_due_sets_a_reminder_but_sends_no_notification(h: _Harness) -> None:
    h.settings.eye_reminder_minutes = 10
    h.session.apply_settings_changed()
    h.session.begin()
    h.session.start_focus(FocusMode.CLASSIC)
    h.clock.advance(minutes=10)
    h.scheduler.tick()

    assert "eyes" in h.session.reminder_text.lower()
    assert h.notifier.sent == []


def test_dismiss_reminder_acknowledges_eye_rest_and_restarts_the_countdown(h: _Harness) -> None:
    h.settings.eye_reminder_minutes = 10
    h.session.apply_settings_changed()
    h.session.begin()
    h.session.start_focus(FocusMode.CLASSIC)
    h.clock.advance(minutes=10)
    h.scheduler.tick()

    h.session.dismiss_reminder()
    assert h.session.reminder_text == ""

    h.clock.advance(minutes=10)
    h.scheduler.tick()
    assert "eyes" in h.session.reminder_text.lower()  # fired again after a full new interval


def test_eye_rest_and_hydration_never_fire_during_an_idea_walk(h: _Harness) -> None:
    h.settings.eye_reminder_minutes = 5
    h.session.apply_settings_changed()
    h.session.begin()
    h.session.start_focus(FocusMode.CLASSIC)
    h.clock.advance(minutes=3)
    h.session.start_idea_walk()

    h.clock.advance(minutes=10)
    h.scheduler.tick()
    assert h.session.reminder_text == ""  # eye-rest was frozen, never fired mid-walk


# -- crash-recovery checkpointing ---------------------------------------------


def test_checkpoint_is_written_immediately_on_a_transition(h: _Harness) -> None:
    h.session.begin()
    h.session.start_focus(FocusMode.CLASSIC, task_label="Design review")
    snapshot = SessionSnapshotRepository(h.db.connection).load()
    assert snapshot is not None
    assert snapshot.task_label == "Design review"


def test_checkpoint_refreshes_at_least_once_per_minute_while_ticking(h: _Harness) -> None:
    h.session.begin()
    h.session.start_focus(FocusMode.CLASSIC)
    first = SessionSnapshotRepository(h.db.connection).load()

    h.clock.advance(seconds=CHECKPOINT_MIN_INTERVAL_SECONDS + 1)
    h.session.tick()
    second = SessionSnapshotRepository(h.db.connection).load()

    assert second is not None
    assert second.last_checkpoint_utc > first.last_checkpoint_utc
    assert second.active_seconds > first.active_seconds


def test_checkpoint_does_not_refire_before_a_minute_has_passed(h: _Harness) -> None:
    h.session.begin()
    h.session.start_focus(FocusMode.CLASSIC)
    first = SessionSnapshotRepository(h.db.connection).load()

    h.clock.advance(seconds=10)
    h.session.tick()
    second = SessionSnapshotRepository(h.db.connection).load()

    assert second.last_checkpoint_utc == first.last_checkpoint_utc


def test_shutdown_persists_a_final_checkpoint(h: _Harness) -> None:
    h.session.begin()
    h.session.start_focus(FocusMode.CLASSIC)
    h.clock.advance(seconds=30)
    h.session.shutdown()
    snapshot = SessionSnapshotRepository(h.db.connection).load()
    assert snapshot.active_seconds == 30


def test_no_checkpoint_is_written_when_nothing_is_in_progress(h: _Harness) -> None:
    h.session.begin()
    h.clock.advance(seconds=CHECKPOINT_MIN_INTERVAL_SECONDS + 5)
    h.session.tick()
    assert SessionSnapshotRepository(h.db.connection).load() is None


# -- idea walk notes -----------------------------------------------------------


def test_idea_walk_note_is_persisted_only_when_provided(h: _Harness) -> None:
    h.session.begin()
    h.session.start_focus(FocusMode.CLASSIC)
    h.session.start_idea_walk()
    h.session.return_from_idea_walk(resume_focus=True, note="split the module in two")

    notes = IdeaWalkNoteRepository(h.db.connection, h.clock).list_recent()
    assert len(notes) == 1
    assert notes[0][1] == "split the module in two"


def test_idea_walk_without_a_note_persists_nothing(h: _Harness) -> None:
    h.session.begin()
    h.session.start_focus(FocusMode.CLASSIC)
    h.session.start_idea_walk()
    h.session.return_from_idea_walk(resume_focus=True)

    notes = IdeaWalkNoteRepository(h.db.connection, h.clock).list_recent()
    assert notes == []


# -- quiet mode -----------------------------------------------------------------


def test_quiet_mode_suppresses_the_recovery_notification_but_not_the_state(h: _Harness) -> None:
    h.session.enter_quiet_mode(minutes=30)
    assert h.session.is_quiet is True

    h.session.begin()
    h.session.start_focus(FocusMode.CLASSIC)
    h.clock.advance(minutes=25)
    h.scheduler.tick()

    assert h.session.focus_state is FocusState.RECOVERY_DUE  # state is still correct
    assert h.notifier.sent == []  # but nothing was announced


def test_quiet_mode_expires_on_its_own(h: _Harness) -> None:
    h.session.enter_quiet_mode(minutes=30)
    h.clock.advance(minutes=31)
    assert h.session.is_quiet is False


def test_exit_quiet_mode_ends_it_immediately(h: _Harness) -> None:
    h.session.enter_quiet_mode(minutes=30)
    h.session.exit_quiet_mode()
    assert h.session.is_quiet is False
    assert h.session.quiet_seconds_remaining == 0.0


def test_quiet_mode_defaults_to_the_configured_quiet_mode_minutes(h: _Harness) -> None:
    h.settings.quiet_mode_minutes = 45
    h.session.enter_quiet_mode()
    assert h.session.quiet_seconds_remaining == pytest.approx(45 * 60)


# -- on_changed notification ---------------------------------------------------


def test_on_changed_fires_for_every_lifecycle_transition(h: _Harness) -> None:
    before = h.changed_count
    h.session.start_focus(FocusMode.CLASSIC)
    assert h.changed_count > before
