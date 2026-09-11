"""Pure aggregation over already-loaded history rows.

``ScreenCare — Technical.md`` section 42: dashboard queries should run only
when the dashboard opens, after a relevant completed event, or when the
user changes the date range — never on a timer. Deliberately split in two
so that rule is easy to honor:
:class:`~screencare.ui.viewmodels.dashboard_view_model.DashboardViewModel`
decides *when* to query the repositories, and this module — no SQLite, no
Qt — turns the rows it got back into the numbers the dashboard actually
shows. Concept.md's "Focus & Wellness Dashboard" wants behavioral patterns,
not raw screen time, so this favors small, explainable counts over a
running total.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from screencare.domain.models import BreakSession, FocusSessionSummary, HydrationEvent


@dataclass(frozen=True)
class DashboardSummary:
    focus_sessions_completed: int
    focus_active_minutes: int
    breaks_taken: int
    away_minutes: int
    hydration_events: int


def dashboard_summary(
    *,
    focus_sessions: list[FocusSessionSummary],
    break_sessions: list[BreakSession],
    hydration_events: list[HydrationEvent],
) -> DashboardSummary:
    """Summarize whatever window of history the caller already fetched
    (typically "today" or "this week" via each repository's ``list_since``).
    Every input list may be empty; the result is then all zeros rather than
    raising, since "nothing recorded yet" is a normal, expected dashboard
    state, not an error."""
    completed = [s for s in focus_sessions if s.outcome.value == "completed"]
    active_seconds = sum(s.active_seconds for s in focus_sessions)
    away_seconds = sum(b.away_seconds for b in break_sessions if b.ended_at_utc is not None)
    return DashboardSummary(
        focus_sessions_completed=len(completed),
        focus_active_minutes=active_seconds // 60,
        breaks_taken=sum(1 for b in break_sessions if b.ended_at_utc is not None),
        away_minutes=away_seconds // 60,
        hydration_events=len(hydration_events),
    )


def start_of_today(now_utc: datetime) -> datetime:
    """Midnight UTC on ``now_utc``'s date — a simple, explainable cutoff for
    "today" rather than trying to reason about the user's local timezone
    inside the aggregation layer."""
    return now_utc.replace(hour=0, minute=0, second=0, microsecond=0)


def start_of_week(now_utc: datetime) -> datetime:
    """Midnight UTC, 7 days back from :func:`start_of_today` — a rolling
    7-day window rather than a calendar week, so "this week" is meaningful
    no matter which day the user opens the dashboard."""
    from datetime import timedelta

    return start_of_today(now_utc) - timedelta(days=6)
