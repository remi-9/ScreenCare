from datetime import UTC, datetime

from screencare.analytics.summary import dashboard_summary, start_of_today, start_of_week
from screencare.domain.enums import BreakCompletionSource, BreakKind, FocusMode, FocusOutcome
from screencare.domain.models import BreakSession, FocusSessionSummary, HydrationEvent


def test_empty_history_summarizes_to_all_zeros() -> None:
    summary = dashboard_summary(focus_sessions=[], break_sessions=[], hydration_events=[])
    assert summary.focus_sessions_completed == 0
    assert summary.focus_active_minutes == 0
    assert summary.breaks_taken == 0
    assert summary.away_minutes == 0
    assert summary.hydration_events == 0


def test_summarizes_completed_sessions_breaks_and_hydration() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    focus_sessions = [
        FocusSessionSummary(
            mode=FocusMode.CLASSIC,
            task_label=None,
            started_at_utc=now,
            ended_at_utc=now,
            planned_seconds=1500,
            active_seconds=1500,
            extension_seconds=0,
            outcome=FocusOutcome.COMPLETED,
        ),
        FocusSessionSummary(
            mode=FocusMode.CLASSIC,
            task_label=None,
            started_at_utc=now,
            ended_at_utc=now,
            planned_seconds=1500,
            active_seconds=300,
            extension_seconds=0,
            outcome=FocusOutcome.ABANDONED,
        ),
    ]
    break_sessions = [
        BreakSession(
            kind=BreakKind.RECOVERY,
            started_at_utc=now,
            ended_at_utc=now,
            away_seconds=300,
            completion_source=BreakCompletionSource.USER_CONFIRMED,
        ),
        BreakSession(kind=BreakKind.AWAY, started_at_utc=now),  # still open -- not counted
    ]
    hydration_events = [HydrationEvent(occurred_at_utc=now, action="logged", source="manual")]

    summary = dashboard_summary(
        focus_sessions=focus_sessions,
        break_sessions=break_sessions,
        hydration_events=hydration_events,
    )
    assert summary.focus_sessions_completed == 1
    assert summary.focus_active_minutes == 30  # (1500 + 300) / 60
    assert summary.breaks_taken == 1
    assert summary.away_minutes == 5
    assert summary.hydration_events == 1


def test_start_of_today_is_midnight_utc() -> None:
    now = datetime(2026, 3, 14, 15, 42, 7, tzinfo=UTC)
    assert start_of_today(now) == datetime(2026, 3, 14, tzinfo=UTC)


def test_start_of_week_is_six_days_before_start_of_today() -> None:
    now = datetime(2026, 3, 14, 15, 42, 7, tzinfo=UTC)
    assert start_of_week(now) == datetime(2026, 3, 8, tzinfo=UTC)
