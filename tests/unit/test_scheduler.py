import pytest

from screencare.scheduler.clock import FakeClock
from screencare.scheduler.scheduler import Scheduler


def test_callback_does_not_fire_before_its_deadline() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    fired = []
    scheduler.schedule_once("a", 60, lambda: fired.append("a"))

    clock.advance(seconds=59)
    assert scheduler.tick() == []
    assert fired == []


def test_callback_fires_once_its_deadline_has_passed() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    fired = []
    scheduler.schedule_once("a", 60, lambda: fired.append("a"))

    clock.advance(seconds=60)
    assert scheduler.tick() == ["a"]
    assert fired == ["a"]

    # It doesn't fire again on a later tick.
    clock.advance(minutes=10)
    assert scheduler.tick() == []
    assert fired == ["a"]


def test_advancing_past_several_deadlines_fires_them_in_due_order() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    fired = []
    scheduler.schedule_once("second", 20, lambda: fired.append("second"))
    scheduler.schedule_once("first", 10, lambda: fired.append("first"))
    scheduler.schedule_once("third", 30, lambda: fired.append("third"))

    clock.advance(seconds=30)
    assert scheduler.tick() == ["first", "second", "third"]
    assert fired == ["first", "second", "third"]


def test_cancel_prevents_a_scheduled_callback_from_firing() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    fired = []
    scheduler.schedule_once("a", 60, lambda: fired.append("a"))

    scheduler.cancel("a")
    clock.advance(minutes=5)
    assert scheduler.tick() == []
    assert fired == []
    assert not scheduler.is_scheduled("a")


def test_scheduling_again_under_the_same_key_replaces_it() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    fired = []
    scheduler.schedule_once("a", 60, lambda: fired.append("first"))
    scheduler.schedule_once("a", 120, lambda: fired.append("second"))

    clock.advance(seconds=60)
    assert scheduler.tick() == []  # the first registration is gone

    clock.advance(seconds=60)
    assert scheduler.tick() == ["a"]
    assert fired == ["second"]


def test_seconds_until_reflects_remaining_time() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    scheduler.schedule_once("a", 90, lambda: None)

    assert scheduler.seconds_until("a") == pytest.approx(90)
    clock.advance(seconds=30)
    assert scheduler.seconds_until("a") == pytest.approx(60)
    assert scheduler.seconds_until("missing") is None


def test_a_callback_rescheduling_its_own_key_is_not_fired_twice_in_one_tick() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    calls = []

    def reschedule_self() -> None:
        calls.append(clock.monotonic_ns())
        scheduler.schedule_once("recurring", 10, reschedule_self)

    scheduler.schedule_once("recurring", 10, reschedule_self)
    clock.advance(seconds=10)
    assert scheduler.tick() == ["recurring"]
    assert len(calls) == 1

    # The rescheduled deadline is 10s further out, not immediately due.
    assert scheduler.tick() == []


def test_negative_delay_is_rejected() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    with pytest.raises(ValueError):
        scheduler.schedule_once("a", -1, lambda: None)
