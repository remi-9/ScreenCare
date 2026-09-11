"""Enums shared across the domain and engine layers.

Kept in one module (rather than scattered per-engine) because several
engines reference the same handful of vocabularies — see
``ScreenCare — Technical.md`` section 6 for the state diagrams these
mirror.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum


class FocusMode(StrEnum):
    """The three focus strategies from ``ScreenCare — Concept.md``."""

    CLASSIC = "classic"
    DEEP_FOCUS = "deep_focus"
    ADAPTIVE = "adaptive"


class FocusState(StrEnum):
    """The focus state machine (``ScreenCare — Technical.md`` section 6)."""

    STOPPED = "stopped"
    FOCUSING = "focusing"
    PAUSED = "paused"
    RECOVERY_DUE = "recovery_due"
    BREAKING = "breaking"
    READY = "ready"
    IDEA_WALK = "idea_walk"


class PresenceState(StrEnum):
    """Presence is deliberately separate from :class:`FocusState` — the
    same focus session can survive several presence changes without its
    visible state changing (``ScreenCare — Technical.md`` section 6)."""

    ACTIVE = "active"
    IDLE = "idle"
    LOCKED = "locked"
    SLEEPING = "sleeping"


class BreakKind(StrEnum):
    RECOVERY = "recovery"
    AWAY = "away"
    IDEA_WALK = "idea_walk"


class BreakCompletionSource(StrEnum):
    """How a break session came to an end. Never inferred to mean more
    than it observed — see ``ScreenCare — Implementation Standards.md``
    section 23 ("Activity and Break Recognition")."""

    USER_CONFIRMED = "user_confirmed"
    IDLE_DETECTED = "idle_detected"
    TIMED_OUT = "timed_out"


class FocusFeedback(StrEnum):
    """Post-session feedback used by Adaptive Focus
    (``ScreenCare — Concept.md``, "Adaptive Focus")."""

    TOO_SHORT = "too_short"
    JUST_RIGHT = "just_right"
    TOO_LONG = "too_long"


class FocusOutcome(StrEnum):
    """How a focus session concluded."""

    COMPLETED = "completed"
    ABANDONED = "abandoned"
    INTERRUPTED = "interrupted"


class NotificationPriority(IntEnum):
    """The four reminder priorities from ``ScreenCare — Technical.md``
    section 8. Higher is more urgent."""

    P0_INFORMATIONAL = 0
    P1_GENTLE = 1
    P2_NORMAL = 2
    P3_RECOVERY_DUE = 3
