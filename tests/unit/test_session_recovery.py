from datetime import datetime, timedelta

from screencare.domain.enums import FocusMode
from screencare.persistence.database import Database
from screencare.persistence.session_recovery import (
    RESUME_WINDOW_SECONDS,
    RecoveryAction,
    SessionSnapshot,
    SessionSnapshotRepository,
    reconcile_startup_snapshot,
)
from screencare.scheduler.clock import FakeClock


def _snapshot(clock: FakeClock, *, active_seconds: int = 300) -> SessionSnapshot:
    return SessionSnapshot(
        mode=FocusMode.CLASSIC,
        task_label="Write tests",
        started_at_utc=clock.utc_now(),
        planned_seconds=1500,
        active_seconds=active_seconds,
        last_checkpoint_utc=clock.utc_now(),
    )


def test_no_snapshot_means_nothing_to_reconcile() -> None:
    outcome = reconcile_startup_snapshot(None, datetime.now())
    assert outcome.action is RecoveryAction.NONE
    assert outcome.snapshot is None
    assert outcome.gap_seconds is None


def test_a_short_gap_offers_to_resume() -> None:
    clock = FakeClock()
    snapshot = _snapshot(clock)
    now = clock.utc_now() + timedelta(seconds=RESUME_WINDOW_SECONDS)
    outcome = reconcile_startup_snapshot(snapshot, now)
    assert outcome.action is RecoveryAction.RESUME_OFFERED
    assert outcome.gap_seconds == RESUME_WINDOW_SECONDS


def test_a_long_gap_is_treated_as_interrupted_not_completed() -> None:
    clock = FakeClock()
    snapshot = _snapshot(clock)
    now = clock.utc_now() + timedelta(seconds=RESUME_WINDOW_SECONDS + 1)
    outcome = reconcile_startup_snapshot(snapshot, now)
    assert outcome.action is RecoveryAction.INTERRUPTED
    # Never claims the session completed — the outcome only ever names
    # NONE / RESUME_OFFERED / INTERRUPTED.
    assert outcome.action is not RecoveryAction.NONE


def test_a_clock_that_appears_to_move_backwards_does_not_crash() -> None:
    clock = FakeClock()
    snapshot = _snapshot(clock)
    now_before_checkpoint = snapshot.last_checkpoint_utc - timedelta(seconds=5)
    outcome = reconcile_startup_snapshot(snapshot, now_before_checkpoint)
    assert outcome.gap_seconds == 0.0
    assert outcome.action is RecoveryAction.RESUME_OFFERED


def test_save_load_and_clear_round_trip() -> None:
    clock = FakeClock()
    db = Database.open_in_memory(clock=clock)
    try:
        repo = SessionSnapshotRepository(db.connection)
        assert repo.load() is None

        snapshot = _snapshot(clock)
        repo.save(snapshot)
        assert repo.load() == snapshot

        repo.clear()
        assert repo.load() is None
    finally:
        db.close()


def test_saving_again_replaces_the_previous_snapshot() -> None:
    clock = FakeClock()
    db = Database.open_in_memory(clock=clock)
    try:
        repo = SessionSnapshotRepository(db.connection)
        repo.save(_snapshot(clock, active_seconds=100))
        clock.advance(minutes=1)
        repo.save(_snapshot(clock, active_seconds=160))

        loaded = repo.load()
        assert loaded is not None
        assert loaded.active_seconds == 160
    finally:
        db.close()
