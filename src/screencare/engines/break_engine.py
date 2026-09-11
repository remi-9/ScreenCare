"""Break session tracking and away-time break qualification.

ScreenCare can't prove someone walked around, so it only ever claims what
it can observe: how long the computer went unused
(``ScreenCare — Implementation Standards.md`` section 23). A "walk
completed" claim requires explicit user confirmation elsewhere — this
engine never invents that on its own.
"""

from __future__ import annotations

from dataclasses import replace

from screencare.domain.enums import BreakCompletionSource, BreakKind
from screencare.domain.errors import InvalidStateTransition
from screencare.domain.models import BreakSession
from screencare.scheduler.clock import Clock

# 3 minutes — ScreenCare — Technical.md section 14 ("Detecting Real Breaks").
AWAY_QUALIFIES_AS_BREAK_SECONDS = 180


class BreakEngine:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def qualifies_as_break(self, away_seconds: float) -> bool:
        """Whether an away period is long enough to count as a meaningful
        computer break, without claiming to know what the user actually
        did during it."""
        return away_seconds >= AWAY_QUALIFIES_AS_BREAK_SECONDS

    def start(self, kind: BreakKind) -> BreakSession:
        return BreakSession(kind=kind, started_at_utc=self._clock.utc_now())

    def end(
        self,
        session: BreakSession,
        *,
        completion_source: BreakCompletionSource,
        away_seconds: int | None = None,
    ) -> BreakSession:
        """Return a concluded copy of ``session``. ``away_seconds``
        defaults to the wall-clock duration of the break itself; pass it
        explicitly when a presence adapter measured actual away time
        (which can differ, e.g. the user was back a moment before
        dismissing the break screen)."""
        if session.ended_at_utc is not None:
            raise InvalidStateTransition("break session is already ended")
        ended_at = self._clock.utc_now()
        computed_away = (
            away_seconds
            if away_seconds is not None
            else max(0, int((ended_at - session.started_at_utc).total_seconds()))
        )
        return replace(
            session,
            ended_at_utc=ended_at,
            away_seconds=computed_away,
            completion_source=completion_source,
        )
