import pytest

from screencare.engines.hydration_engine import HydrationEngine, HydrationSettings
from screencare.scheduler.clock import FakeClock
from screencare.scheduler.scheduler import Scheduler


def test_becomes_due_after_the_configured_interval() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    engine = HydrationEngine(clock, scheduler, settings=HydrationSettings(interval_seconds=60 * 60))
    engine.start()

    clock.advance(minutes=59)
    scheduler.tick()
    assert not engine.is_due

    clock.advance(minutes=1)
    scheduler.tick()
    assert engine.is_due


def test_on_due_callback_fires() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    calls = []
    engine = HydrationEngine(
        clock,
        scheduler,
        settings=HydrationSettings(interval_seconds=60),
        on_due=lambda: calls.append("due"),
    )
    engine.start()
    clock.advance(minutes=1)
    scheduler.tick()
    assert calls == ["due"]


def test_log_drink_resets_the_interval_and_clears_due() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    engine = HydrationEngine(clock, scheduler, settings=HydrationSettings(interval_seconds=60 * 60))
    engine.start()
    clock.advance(minutes=60)
    scheduler.tick()
    assert engine.is_due

    event = engine.log_drink(source="manual")
    assert event.occurred_at_utc == clock.utc_now()
    assert event.source == "manual"
    assert not engine.is_due
    assert engine.seconds_until_due == pytest.approx(60 * 60)


def test_freeze_and_resume_pause_the_countdown() -> None:
    clock = FakeClock()
    scheduler = Scheduler(clock)
    engine = HydrationEngine(clock, scheduler, settings=HydrationSettings(interval_seconds=60 * 60))
    engine.start()
    clock.advance(minutes=45)
    engine.freeze()

    clock.advance(hours=2)  # asleep for a while
    scheduler.tick()
    assert not engine.is_due  # frozen, so no callback should have fired

    engine.resume()
    assert engine.seconds_until_due == pytest.approx(15 * 60)
    clock.advance(minutes=15)
    scheduler.tick()
    assert engine.is_due


def test_settings_reject_invalid_values() -> None:
    with pytest.raises(ValueError):
        HydrationSettings(interval_seconds=0)
    with pytest.raises(ValueError):
        HydrationSettings(merge_window_seconds=-1)
