"""Subtle, non-disruptive eye-rest prompts during a focus session.

These never end the session or fire as an OS-level notification
(``ScreenCare — Concept.md``, "Micro Eye Breaks") — this engine only tracks
*when* a prompt is due; how gently it's shown is a Phase 4 concern.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from screencare.scheduler.clock import Clock
from screencare.scheduler.deadline_budget import DeadlineBudget
from screencare.scheduler.scheduler import Scheduler

_DUE_KEY = "eye_rest_due"


@dataclass(frozen=True)
class EyeRestSettings:
    # "approximately every 20 minutes" — ScreenCare — Concept.md.
    interval_seconds: int = 20 * 60
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")


class EyeRestEngine:
    def __init__(
        self,
        clock: Clock,
        scheduler: Scheduler,
        *,
        settings: EyeRestSettings | None = None,
        on_due: Callable[[], None] | None = None,
    ) -> None:
        self._clock = clock
        self.settings = settings or EyeRestSettings()
        self._on_due = on_due or (lambda: None)
        self._budget = DeadlineBudget(clock, scheduler, _DUE_KEY, self._handle_due)
        self._due = False

    def start(self) -> None:
        """Arm the countdown to the next prompt. A no-op if disabled —
        users must be able to turn these off entirely
        (``ScreenCare — Implementation Standards.md`` section 22)."""
        self._due = False
        if self.settings.enabled:
            self._budget.arm(self.settings.interval_seconds)

    def stop(self) -> None:
        """Cancel outright (e.g. the focus session paused or ended)."""
        self._budget.cancel()
        self._due = False

    def freeze(self) -> None:
        self._budget.freeze()

    def resume(self) -> None:
        if self.settings.enabled and not self._budget.armed:
            self._budget.arm(self._budget.remaining_seconds or self.settings.interval_seconds)

    def acknowledge(self) -> None:
        """The prompt was seen (or auto-dismissed); start the next one."""
        self.start()

    def snooze(self, seconds: float) -> None:
        self._due = False
        self._budget.arm(seconds)

    @property
    def is_due(self) -> bool:
        return self._due

    @property
    def seconds_until_due(self) -> float | None:
        return self._budget.remaining_seconds if self._budget.armed else None

    def _handle_due(self) -> None:
        self._due = True
        self._on_due()
