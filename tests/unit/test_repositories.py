import pytest

from screencare.domain.enums import (
    BreakCompletionSource,
    BreakKind,
    FocusFeedback,
    FocusMode,
    FocusOutcome,
)
from screencare.domain.models import BreakSession, FocusSessionSummary, HydrationEvent
from screencare.persistence.database import Database
from screencare.persistence.repositories import (
    BreakSessionRepository,
    FocusSessionRepository,
    HydrationEventRepository,
    IdeaWalkNoteRepository,
)
from screencare.scheduler.clock import FakeClock


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def db(clock: FakeClock):
    database = Database.open_in_memory(clock=clock)
    yield database
    database.close()


def test_focus_session_round_trips(db, clock) -> None:
    repo = FocusSessionRepository(db.connection, clock)
    summary = FocusSessionSummary(
        mode=FocusMode.CLASSIC,
        task_label="Write tests",
        started_at_utc=clock.utc_now(),
        ended_at_utc=clock.utc_now(),
        planned_seconds=1500,
        active_seconds=1500,
        extension_seconds=0,
        outcome=FocusOutcome.COMPLETED,
        feedback=FocusFeedback.JUST_RIGHT,
    )
    row_id = repo.insert(summary)
    assert row_id

    (persisted,) = repo.list_recent()
    assert persisted == summary


def test_focus_session_without_feedback_round_trips(db, clock) -> None:
    repo = FocusSessionRepository(db.connection, clock)
    summary = FocusSessionSummary(
        mode=FocusMode.DEEP_FOCUS,
        task_label=None,
        started_at_utc=clock.utc_now(),
        ended_at_utc=clock.utc_now(),
        planned_seconds=3000,
        active_seconds=600,
        extension_seconds=300,
        outcome=FocusOutcome.ABANDONED,
    )
    repo.insert(summary)
    (persisted,) = repo.list_recent()
    assert persisted.feedback is None
    assert persisted.task_label is None
    assert persisted.outcome is FocusOutcome.ABANDONED


def test_list_recent_orders_newest_first_and_respects_limit(db, clock) -> None:
    repo = FocusSessionRepository(db.connection, clock)
    for i in range(3):
        clock.advance(minutes=1)
        repo.insert(
            FocusSessionSummary(
                mode=FocusMode.CLASSIC,
                task_label=f"session {i}",
                started_at_utc=clock.utc_now(),
                ended_at_utc=clock.utc_now(),
                planned_seconds=1500,
                active_seconds=1500,
                extension_seconds=0,
                outcome=FocusOutcome.COMPLETED,
            )
        )
    results = repo.list_recent(limit=2)
    assert len(results) == 2
    assert results[0].task_label == "session 2"
    assert results[1].task_label == "session 1"


def test_break_session_round_trips(db, clock) -> None:
    repo = BreakSessionRepository(db.connection, clock)
    session = BreakSession(
        kind=BreakKind.RECOVERY,
        started_at_utc=clock.utc_now(),
        ended_at_utc=clock.utc_now(),
        away_seconds=300,
        completion_source=BreakCompletionSource.USER_CONFIRMED,
    )
    repo.insert(session)
    (persisted,) = repo.list_recent()
    assert persisted == session


def test_break_session_must_be_ended_before_persisting(db, clock) -> None:
    repo = BreakSessionRepository(db.connection, clock)
    open_session = BreakSession(kind=BreakKind.AWAY, started_at_utc=clock.utc_now())
    with pytest.raises(ValueError):
        repo.insert(open_session)


def test_hydration_event_round_trips(db) -> None:
    repo = HydrationEventRepository(db.connection)
    clock = FakeClock()
    event = HydrationEvent(occurred_at_utc=clock.utc_now(), action="logged", source="manual")
    repo.insert(event)
    (persisted,) = repo.list_recent()
    assert persisted == event


def test_list_since_excludes_entries_before_the_cutoff(db, clock) -> None:
    repo = FocusSessionRepository(db.connection, clock)
    repo.insert(
        FocusSessionSummary(
            mode=FocusMode.CLASSIC,
            task_label="too old",
            started_at_utc=clock.utc_now(),
            ended_at_utc=clock.utc_now(),
            planned_seconds=1500,
            active_seconds=1500,
            extension_seconds=0,
            outcome=FocusOutcome.COMPLETED,
        )
    )

    clock.advance(minutes=10)
    cutoff = clock.utc_now()
    clock.advance(minutes=5)

    repo.insert(
        FocusSessionSummary(
            mode=FocusMode.CLASSIC,
            task_label="recent enough",
            started_at_utc=clock.utc_now(),
            ended_at_utc=clock.utc_now(),
            planned_seconds=1500,
            active_seconds=1500,
            extension_seconds=0,
            outcome=FocusOutcome.COMPLETED,
        )
    )

    (only,) = repo.list_since(cutoff)
    assert only.task_label == "recent enough"


def test_idea_walk_note_round_trips(db, clock) -> None:
    repo = IdeaWalkNoteRepository(db.connection, clock)
    repo.insert("maybe split the module in two")
    (persisted,) = repo.list_recent()
    occurred_at, note = persisted
    assert note == "maybe split the module in two"
    assert occurred_at == clock.utc_now()
