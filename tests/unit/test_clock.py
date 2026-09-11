from datetime import UTC, datetime

import pytest

from screencare.scheduler.clock import FakeClock


def test_fake_clock_starts_at_a_fixed_point() -> None:
    clock = FakeClock()
    assert clock.monotonic_ns() == 0
    assert clock.utc_now() == datetime(2026, 1, 1, tzinfo=UTC)


def test_fake_clock_accepts_a_custom_start() -> None:
    start = datetime(2030, 6, 15, 12, 0, tzinfo=UTC)
    clock = FakeClock(start_utc=start)
    assert clock.utc_now() == start


def test_advance_moves_both_monotonic_and_utc_time() -> None:
    clock = FakeClock()
    clock.advance(minutes=50)
    assert clock.monotonic_ns() == 50 * 60 * 1_000_000_000
    assert clock.utc_now() == datetime(2026, 1, 1, 0, 50, tzinfo=UTC)


def test_advance_accumulates_across_calls() -> None:
    clock = FakeClock()
    clock.advance(seconds=30)
    clock.advance(minutes=1)
    assert clock.monotonic_ns() == 90 * 1_000_000_000


def test_advance_rejects_negative_durations() -> None:
    clock = FakeClock()
    with pytest.raises(ValueError, match="backwards"):
        clock.advance(seconds=-1)
