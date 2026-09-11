"""A remaining-time budget whose scheduled deadline can freeze and thaw.

Several engines need the same "don't let sleep/idle/lock count against the
user" behavior (``ScreenCare — Technical.md`` section 12): the focus timer,
hourly hydration, and the eye-rest interval. Rather than each reimplement
freeze/thaw arithmetic on top of :class:`~screencare.scheduler.scheduler.Scheduler`,
they each wrap one of these around it. Presence detection itself doesn't
exist until Phase 5 — callers (tests today, the activity monitor later)
simply call :meth:`freeze` / :meth:`arm` when presence changes.
"""

from __future__ import annotations

from collections.abc import Callable

from screencare.scheduler.clock import Clock
from screencare.scheduler.scheduler import Scheduler


class DeadlineBudget:
    def __init__(
        self,
        clock: Clock,
        scheduler: Scheduler,
        key: str,
        on_due: Callable[[], None],
    ) -> None:
        self._clock = clock
        self._scheduler = scheduler
        self._key = key
        self._on_due = on_due
        self._remaining_seconds = 0.0
        self._armed = False

    @property
    def armed(self) -> bool:
        return self._armed

    @property
    def remaining_seconds(self) -> float:
        """The current remaining budget. Live (ticking down) while armed;
        frozen at its last value otherwise."""
        if self._armed:
            live = self._scheduler.seconds_until(self._key)
            return max(0.0, live) if live is not None else self._remaining_seconds
        return self._remaining_seconds

    def arm(self, remaining_seconds: float) -> None:
        """(Re)schedule the deadline ``remaining_seconds`` from now."""
        if remaining_seconds < 0:
            raise ValueError(f"remaining_seconds must be >= 0, got {remaining_seconds!r}")
        self._remaining_seconds = remaining_seconds
        self._scheduler.schedule_once(self._key, remaining_seconds, self._fire)
        self._armed = True

    def freeze(self) -> float:
        """Cancel the scheduled deadline, preserving the remaining budget
        for a later :meth:`arm`. Returns that remaining budget. Safe to
        call when not armed (returns the last-known value)."""
        if self._armed:
            live = self._scheduler.seconds_until(self._key)
            if live is not None:
                self._remaining_seconds = max(0.0, live)
            self._scheduler.cancel(self._key)
            self._armed = False
        return self._remaining_seconds

    def cancel(self) -> None:
        """Cancel outright and reset the remaining budget to zero — the
        deadline is done with, not just paused."""
        self._scheduler.cancel(self._key)
        self._armed = False
        self._remaining_seconds = 0.0

    def _fire(self) -> None:
        self._armed = False
        self._remaining_seconds = 0.0
        self._on_due()
