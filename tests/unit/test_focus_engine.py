import pytest

from screencare.domain.enums import FocusMode, FocusOutcome, FocusState, PresenceState
from screencare.domain.errors import InvalidStateTransition
from screencare.domain.models import FocusDurations, FocusPlan
from screencare.engines.focus_engine import FocusEngine
from screencare.scheduler.clock import FakeClock
from screencare.scheduler.scheduler import Scheduler

PLAN = FocusPlan(
    mode=FocusMode.CLASSIC,
    durations=FocusDurations(25 * 60, 5 * 60),
    task_label="Write tests",
)


def _make() -> tuple[FakeClock, Scheduler, FocusEngine]:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    engine = FocusEngine(clock, scheduler)
    return clock, scheduler, engine


def test_starts_in_stopped_state() -> None:
    _, _, engine = _make()
    assert engine.state is FocusState.STOPPED
    assert engine.plan is None
    assert engine.started_at_utc is None


def test_plan_and_started_at_are_exposed_once_a_session_starts() -> None:
    clock, _, engine = _make()
    engine.start(PLAN)
    assert engine.plan == PLAN
    assert engine.started_at_utc == clock.utc_now()


def test_full_happy_path_classic_session() -> None:
    clock, scheduler, engine = _make()
    engine.start(PLAN)
    assert engine.state is FocusState.FOCUSING

    clock.advance(minutes=25)
    scheduler.tick()
    assert engine.state is FocusState.RECOVERY_DUE

    engine.start_break()
    assert engine.state is FocusState.BREAKING

    clock.advance(minutes=5)
    summary = engine.end_break()
    assert engine.state is FocusState.READY
    assert summary.outcome is FocusOutcome.COMPLETED
    assert summary.active_seconds == 25 * 60
    assert summary.planned_seconds == 25 * 60
    assert summary.task_label == "Write tests"

    engine.acknowledge_ready()
    assert engine.state is FocusState.STOPPED


def test_pause_freezes_active_time_and_resume_continues_it() -> None:
    clock, scheduler, engine = _make()
    engine.start(PLAN)
    clock.advance(minutes=10)
    engine.pause()
    assert engine.state is FocusState.PAUSED
    assert engine.active_seconds == 10 * 60

    # Time passing while paused must not count as focus time.
    clock.advance(hours=2)
    assert engine.active_seconds == 10 * 60

    engine.resume()
    assert engine.state is FocusState.FOCUSING
    clock.advance(minutes=15)
    scheduler.tick()
    assert engine.state is FocusState.RECOVERY_DUE
    assert engine.active_seconds == 25 * 60


def test_pause_is_only_valid_while_focusing() -> None:
    _, _, engine = _make()
    with pytest.raises(InvalidStateTransition):
        engine.pause()


def test_extend_adds_time_and_is_capped() -> None:
    clock, scheduler, engine = _make()
    engine.start(PLAN)
    clock.advance(minutes=25)
    scheduler.tick()
    assert engine.state is FocusState.RECOVERY_DUE

    assert engine.extend(5 * 60) == 1
    assert engine.state is FocusState.FOCUSING
    clock.advance(minutes=5)
    scheduler.tick()
    assert engine.state is FocusState.RECOVERY_DUE

    assert engine.extend(5 * 60) == 2  # default max_extensions is 2
    clock.advance(minutes=5)
    scheduler.tick()
    assert engine.state is FocusState.RECOVERY_DUE

    with pytest.raises(InvalidStateTransition):
        engine.extend(5 * 60)


def test_finish_current_thought_grants_a_grace_period_once() -> None:
    clock, scheduler, engine = _make()
    engine.start(PLAN)
    clock.advance(minutes=25)
    scheduler.tick()

    engine.finish_current_thought(60)
    assert engine.state is FocusState.FOCUSING
    clock.advance(seconds=60)
    scheduler.tick()
    assert engine.state is FocusState.RECOVERY_DUE

    engine.start_break()
    engine.end_break()
    engine.acknowledge_ready()

    # A brand new session gets its own grace period again.
    engine.start(PLAN)
    clock.advance(minutes=25)
    scheduler.tick()
    engine.finish_current_thought(60)  # does not raise
    clock.advance(seconds=60)
    scheduler.tick()

    with pytest.raises(InvalidStateTransition):
        engine.finish_current_thought(60)


def test_idea_walk_manual_return_resumes_the_remaining_budget() -> None:
    clock, scheduler, engine = _make()
    engine.start(PLAN)
    clock.advance(minutes=10)
    remaining_before = engine.remaining_seconds

    engine.start_idea_walk()
    assert engine.state is FocusState.IDEA_WALK
    clock.advance(minutes=3)  # well within the 5-minute idea walk window

    result = engine.return_from_idea_walk(resume_focus=True)
    assert result is None
    assert engine.state is FocusState.FOCUSING
    assert engine.remaining_seconds == pytest.approx(remaining_before, abs=1)

    # Time spent on the idea walk itself must not count as focus time.
    assert engine.active_seconds == pytest.approx(10 * 60, abs=1)


def test_idea_walk_can_end_the_session_instead_of_resuming() -> None:
    clock, _, engine = _make()
    engine.start(PLAN)
    clock.advance(minutes=10)
    engine.start_idea_walk()
    clock.advance(minutes=2)

    summary = engine.return_from_idea_walk(resume_focus=False)
    assert summary is not None
    assert summary.outcome.value == "interrupted"
    assert engine.state is FocusState.READY


def test_idea_walk_times_out_and_automatically_resumes_focus() -> None:
    clock, scheduler, engine = _make()
    engine.start(PLAN)
    clock.advance(minutes=10)
    engine.start_idea_walk()

    clock.advance(minutes=5)  # default idea walk duration
    scheduler.tick()
    assert engine.state is FocusState.FOCUSING


def test_stop_from_focusing_marks_the_session_abandoned() -> None:
    clock, _, engine = _make()
    engine.start(PLAN)
    clock.advance(minutes=5)
    summary = engine.stop()
    assert summary is not None
    assert summary.outcome is FocusOutcome.ABANDONED
    assert summary.active_seconds == 5 * 60
    assert engine.state is FocusState.STOPPED


def test_stop_when_already_stopped_is_a_no_op() -> None:
    _, _, engine = _make()
    assert engine.stop() is None
    assert engine.state is FocusState.STOPPED


def test_invalid_transitions_raise() -> None:
    _, _, engine = _make()
    with pytest.raises(InvalidStateTransition):
        engine.start_break()
    with pytest.raises(InvalidStateTransition):
        engine.end_break()
    with pytest.raises(InvalidStateTransition):
        engine.resume()
    with pytest.raises(InvalidStateTransition):
        engine.start_idea_walk()


# -- The Phase 1 acceptance scenario: sleep must never count as focus time --


def test_sleeping_mid_session_does_not_count_as_focus_time() -> None:
    """ScreenCare — Technical.md section 47, "Timer correctness":
    start a 25-minute session, sleep 30 minutes, wake up — the sleep must
    not be counted as active computer use, and the session must not
    complete just because 30 minutes of wall-clock time passed.
    """
    clock, scheduler, engine = _make()
    engine.start(PLAN)
    clock.advance(minutes=5)
    assert engine.active_seconds == 5 * 60

    engine.on_presence_changed(PresenceState.SLEEPING)
    clock.advance(minutes=30)
    scheduler.tick()

    # Still focusing — nowhere near the 25 real minutes of *active* work,
    # even though 35 minutes of wall-clock time have now passed.
    assert engine.state is FocusState.FOCUSING
    assert engine.active_seconds == 5 * 60

    away_seconds = engine.on_presence_changed(PresenceState.ACTIVE)
    assert away_seconds == pytest.approx(30 * 60)
    assert engine.active_seconds == 5 * 60

    # The remaining 20 minutes of *active* work still need to happen.
    clock.advance(minutes=20)
    scheduler.tick()
    assert engine.state is FocusState.RECOVERY_DUE
    assert engine.active_seconds == 25 * 60


def test_presence_changes_while_paused_do_not_affect_accounting() -> None:
    clock, scheduler, engine = _make()
    engine.start(PLAN)
    clock.advance(minutes=5)
    engine.pause()

    engine.on_presence_changed(PresenceState.SLEEPING)
    clock.advance(hours=3)
    engine.on_presence_changed(PresenceState.ACTIVE)
    scheduler.tick()

    assert engine.state is FocusState.PAUSED
    assert engine.active_seconds == 5 * 60

    engine.resume()
    clock.advance(minutes=20)
    scheduler.tick()
    assert engine.state is FocusState.RECOVERY_DUE
