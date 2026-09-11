import pytest

from screencare.engines.eye_rest_engine import EyeRestEngine, EyeRestSettings
from screencare.scheduler.clock import FakeClock
from screencare.scheduler.scheduler import Scheduler


def test_becomes_due_after_the_configured_interval() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    engine = EyeRestEngine(clock, scheduler, settings=EyeRestSettings(interval_seconds=20 * 60))
    engine.start()

    clock.advance(minutes=19)
    scheduler.tick()
    assert not engine.is_due

    clock.advance(minutes=1)
    scheduler.tick()
    assert engine.is_due


def test_disabled_engine_never_arms() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    engine = EyeRestEngine(clock, scheduler, settings=EyeRestSettings(enabled=False))
    engine.start()
    assert engine.seconds_until_due is None

    clock.advance(hours=5)
    scheduler.tick()
    assert not engine.is_due


def test_acknowledge_clears_due_and_restarts_the_interval() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    engine = EyeRestEngine(clock, scheduler, settings=EyeRestSettings(interval_seconds=60))
    engine.start()
    clock.advance(minutes=1)
    scheduler.tick()
    assert engine.is_due

    engine.acknowledge()
    assert not engine.is_due
    assert engine.seconds_until_due == pytest.approx(60)


def test_snooze_delays_the_next_prompt() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    engine = EyeRestEngine(clock, scheduler, settings=EyeRestSettings(interval_seconds=60))
    engine.start()
    clock.advance(minutes=1)
    scheduler.tick()
    assert engine.is_due

    engine.snooze(300)
    assert not engine.is_due
    clock.advance(seconds=299)
    scheduler.tick()
    assert not engine.is_due
    clock.advance(seconds=1)
    scheduler.tick()
    assert engine.is_due


def test_stop_cancels_the_countdown() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    engine = EyeRestEngine(clock, scheduler, settings=EyeRestSettings(interval_seconds=60))
    engine.start()
    engine.stop()
    clock.advance(minutes=5)
    scheduler.tick()
    assert not engine.is_due
    assert engine.seconds_until_due is None
