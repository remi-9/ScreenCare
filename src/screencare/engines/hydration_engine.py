"""Hourly-by-default hydration reminder.

Whether a due reminder should fire on its own or be merged into an
upcoming recovery break is decided by
:class:`~screencare.engines.wellness_coordinator.WellnessCoordinator`, not
here — this engine only tracks *when* hydration becomes due and lets the
user log a drink to reset the interval (``ScreenCare — Technical.md``
section 9).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from screencare.domain.models import HydrationEvent
from screencare.scheduler.clock import Clock
from screencare.scheduler.deadline_budget import DeadlineBudget
from screencare.scheduler.scheduler import Scheduler

_DUE_KEY = "hydration_due"


@dataclass(frozen=True)
class HydrationSettings:
    """Defaults from ``ScreenCare — Technical.md`` section 9."""

    interval_seconds: int = 60 * 60
    merge_window_seconds: int = 10 * 60
    max_defer_seconds: int = 10 * 60
    strict: bool = False

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        if self.merge_window_seconds < 0 or self.max_defer_seconds < 0:
            raise ValueError("merge_window_seconds/max_defer_seconds must not be negative")


class HydrationEngine:
    def __init__(
        self,
        clock: Clock,
        scheduler: Scheduler,
        *,
        settings: HydrationSettings | None = None,
        on_due: Callable[[], None] | None = None,
    ) -> None:
        self._clock = clock
        self.settings = settings or HydrationSettings()
        self._on_due = on_due or (lambda: None)
        self._budget = DeadlineBudget(clock, scheduler, _DUE_KEY, self._handle_due)
        self._due = False

    def start(self) -> None:
        """Arm (or re-arm) the countdown to the next hydration reminder."""
        self._due = False
        self._budget.arm(self.settings.interval_seconds)

    def freeze(self) -> None:
        """Stop the countdown (e.g. the system is asleep or locked)."""
        self._budget.freeze()

    def resume(self) -> None:
        """Resume a frozen countdown from wherever it was left. If hydration
        was already due (and not yet re-armed by :meth:`log_drink` or
        :meth:`start`) rather than actually frozen mid-countdown,
        ``remaining_seconds`` is ``0`` — fall back to a full interval rather
        than re-arming for zero seconds, which would just fire again
        immediately (mirrors :meth:`~screencare.engines.eye_rest_engine.EyeRestEngine.resume`)."""
        if not self._budget.armed:
            self._budget.arm(self._budget.remaining_seconds or self.settings.interval_seconds)

    def log_drink(self, *, source: str = "manual") -> HydrationEvent:
        """Record a hydration action and reset the interval."""
        event = HydrationEvent(
            occurred_at_utc=self._clock.utc_now(), action="logged", source=source
        )
        self.start()
        return event

    @property
    def is_due(self) -> bool:
        return self._due

    @property
    def seconds_until_due(self) -> float:
        return self._budget.remaining_seconds

    def _handle_due(self) -> None:
        self._due = True
        self._on_due()
