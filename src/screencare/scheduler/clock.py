"""Clock abstraction.

``ScreenCare — Technical.md`` section 11 and
``ScreenCare — Implementation Standards.md`` section 7 are explicit: never
use a decrementing counter as the source of timer truth, and never make
tests wait on a real clock. Everything time-sensitive in this codebase
takes a :class:`Clock` rather than calling :mod:`time` or
:class:`datetime.datetime` directly, so production code uses
:class:`SystemClock` and tests use :class:`FakeClock`.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    """A source of both monotonic and wall-clock time.

    Monotonic time is for measuring elapsed durations within a run (it
    can't go backwards and isn't affected by clock changes); UTC time is
    for anything persisted or shown to the user, and for reconciling state
    across a restart or sleep/wake cycle.
    """

    def monotonic_ns(self) -> int: ...

    def utc_now(self) -> datetime: ...


class SystemClock:
    """Production clock, backed by the real system clocks."""

    def monotonic_ns(self) -> int:
        return time.monotonic_ns()

    def utc_now(self) -> datetime:
        return datetime.now(UTC)


class FakeClock:
    """Deterministic clock for tests.

    Advance it explicitly instead of waiting on a real clock — see
    ``ScreenCare — Implementation Standards.md`` section 36:

    >>> clock = FakeClock()
    >>> clock.advance(minutes=50)
    """

    def __init__(self, start_utc: datetime | None = None) -> None:
        self._monotonic_ns = 0
        self._utc = start_utc if start_utc is not None else datetime(2026, 1, 1, tzinfo=UTC)

    def monotonic_ns(self) -> int:
        return self._monotonic_ns

    def utc_now(self) -> datetime:
        return self._utc

    def advance(self, *, seconds: float = 0, minutes: float = 0, hours: float = 0) -> None:
        delta = timedelta(seconds=seconds, minutes=minutes, hours=hours)
        if delta.total_seconds() < 0:
            raise ValueError("FakeClock cannot move backwards")
        self._monotonic_ns += int(delta.total_seconds() * 1_000_000_000)
        self._utc += delta
