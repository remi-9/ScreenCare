import pytest

from screencare.domain.enums import BreakCompletionSource, BreakKind
from screencare.domain.errors import InvalidStateTransition
from screencare.engines.break_engine import AWAY_QUALIFIES_AS_BREAK_SECONDS, BreakEngine
from screencare.scheduler.clock import FakeClock


def test_away_period_shorter_than_threshold_does_not_qualify() -> None:
    engine = BreakEngine(FakeClock())
    assert not engine.qualifies_as_break(AWAY_QUALIFIES_AS_BREAK_SECONDS - 1)


def test_away_period_at_or_above_threshold_qualifies() -> None:
    engine = BreakEngine(FakeClock())
    assert engine.qualifies_as_break(AWAY_QUALIFIES_AS_BREAK_SECONDS)
    assert engine.qualifies_as_break(AWAY_QUALIFIES_AS_BREAK_SECONDS + 60)


def test_start_records_the_current_time_and_leaves_the_session_open() -> None:
    clock = FakeClock()
    engine = BreakEngine(clock)
    session = engine.start(BreakKind.RECOVERY)
    assert session.kind is BreakKind.RECOVERY
    assert session.started_at_utc == clock.utc_now()
    assert session.ended_at_utc is None


def test_end_computes_away_seconds_from_elapsed_wall_clock_time_by_default() -> None:
    clock = FakeClock()
    engine = BreakEngine(clock)
    session = engine.start(BreakKind.RECOVERY)
    clock.advance(minutes=7)
    ended = engine.end(session, completion_source=BreakCompletionSource.USER_CONFIRMED)
    assert ended.away_seconds == 7 * 60
    assert ended.ended_at_utc == clock.utc_now()
    assert ended.completion_source is BreakCompletionSource.USER_CONFIRMED


def test_end_accepts_an_explicit_away_seconds_override() -> None:
    clock = FakeClock()
    engine = BreakEngine(clock)
    session = engine.start(BreakKind.AWAY)
    clock.advance(minutes=10)
    ended = engine.end(
        session,
        completion_source=BreakCompletionSource.IDLE_DETECTED,
        away_seconds=42,
    )
    assert ended.away_seconds == 42


def test_ending_an_already_ended_session_raises() -> None:
    clock = FakeClock()
    engine = BreakEngine(clock)
    session = engine.start(BreakKind.RECOVERY)
    ended = engine.end(session, completion_source=BreakCompletionSource.TIMED_OUT)
    with pytest.raises(InvalidStateTransition):
        engine.end(ended, completion_source=BreakCompletionSource.TIMED_OUT)
