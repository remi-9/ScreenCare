"""Plain-data domain models.

These deliberately mirror the shape of the persistence tables in
``ScreenCare — Technical.md`` section 21 (``focus_sessions``,
``break_sessions``, ``hydration_events``) so Phase 3 can persist them with
no translation layer — but nothing in this module touches SQLite, Qt, or
any OS API.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from screencare.domain.enums import (
    BreakCompletionSource,
    BreakKind,
    FocusFeedback,
    FocusMode,
    FocusOutcome,
)


@dataclass(frozen=True)
class FocusDurations:
    """A focus/recovery duration pair, in seconds."""

    focus_seconds: int
    recovery_seconds: int

    def __post_init__(self) -> None:
        if self.focus_seconds <= 0 or self.recovery_seconds <= 0:
            raise ValueError("focus_seconds and recovery_seconds must be positive")


@dataclass(frozen=True)
class FocusPlan:
    """What a focus session was started with."""

    mode: FocusMode
    durations: FocusDurations
    task_label: str | None = None


# Defaults from ScreenCare — Concept.md / Technical.md section 10. Adaptive
# mode's *focus* duration comes from AdaptiveFocusEngine instead of a fixed
# constant; ADAPTIVE_DEFAULT_RECOVERY_SECONDS is a starting point for its
# recovery duration, which the spec doesn't otherwise pin down.
CLASSIC_DURATIONS = FocusDurations(focus_seconds=25 * 60, recovery_seconds=5 * 60)
DEEP_FOCUS_DURATIONS = FocusDurations(focus_seconds=50 * 60, recovery_seconds=8 * 60)
ADAPTIVE_DEFAULT_RECOVERY_SECONDS = 7 * 60


@dataclass(frozen=True)
class FocusSessionSummary:
    """A concluded focus session."""

    mode: FocusMode
    task_label: str | None
    started_at_utc: datetime
    ended_at_utc: datetime
    planned_seconds: int
    active_seconds: int
    extension_seconds: int
    outcome: FocusOutcome
    feedback: FocusFeedback | None = None

    @property
    def completion_rate(self) -> float:
        """``active_seconds`` as a fraction of ``planned_seconds``, the
        input Adaptive Focus needs (``ScreenCare — Technical.md``
        section 10)."""
        if self.planned_seconds <= 0:
            return 0.0
        return self.active_seconds / self.planned_seconds


@dataclass(frozen=True)
class BreakSession:
    """A break, in progress or concluded."""

    kind: BreakKind
    started_at_utc: datetime
    ended_at_utc: datetime | None = None
    away_seconds: int = 0
    completion_source: BreakCompletionSource | None = None


@dataclass(frozen=True)
class HydrationEvent:
    """A single hydration action (a logged drink, most commonly)."""

    occurred_at_utc: datetime
    action: str
    source: str
