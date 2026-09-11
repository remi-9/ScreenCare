import pytest

from screencare.scheduler.clock import FakeClock
from screencare.scheduler.deadline_budget import DeadlineBudget
from screencare.scheduler.scheduler import Scheduler


def _make() -> tuple[FakeClock, Scheduler, list[str], DeadlineBudget]:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    fired: list[str] = []
    budget = DeadlineBudget(clock, scheduler, "test", lambda: fired.append("due"))
    return clock, scheduler, fired, budget


def test_arm_schedules_and_fires_after_the_given_duration() -> None:
    clock, scheduler, fired, budget = _make()
    budget.arm(60)
    assert budget.armed
    clock.advance(seconds=59)
    scheduler.tick()
    assert fired == []
    clock.advance(seconds=1)
    scheduler.tick()
    assert fired == ["due"]
    assert not budget.armed


def test_freeze_preserves_remaining_time_for_a_later_arm() -> None:
    clock, scheduler, fired, budget = _make()
    budget.arm(100)
    clock.advance(seconds=40)
    remaining = budget.freeze()
    assert remaining == pytest.approx(60)
    assert not budget.armed

    # Time passing while frozen must not consume any of the budget.
    clock.advance(hours=1)
    scheduler.tick()
    assert fired == []
    assert budget.remaining_seconds == pytest.approx(60)

    budget.arm(budget.remaining_seconds)
    clock.advance(seconds=60)
    scheduler.tick()
    assert fired == ["due"]


def test_freeze_when_not_armed_is_a_safe_no_op() -> None:
    _, _, _, budget = _make()
    assert budget.freeze() == 0.0
    assert not budget.armed


def test_cancel_resets_remaining_time_to_zero() -> None:
    clock, scheduler, fired, budget = _make()
    budget.arm(100)
    clock.advance(seconds=10)
    budget.cancel()
    assert not budget.armed
    assert budget.remaining_seconds == 0.0

    clock.advance(hours=1)
    scheduler.tick()
    assert fired == []


def test_remaining_seconds_counts_down_live_while_armed() -> None:
    clock, _, _, budget = _make()
    budget.arm(100)
    clock.advance(seconds=25)
    assert budget.remaining_seconds == pytest.approx(75)


def test_arm_rejects_a_negative_duration() -> None:
    _, _, _, budget = _make()
    with pytest.raises(ValueError):
        budget.arm(-1)
