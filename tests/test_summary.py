from datetime import UTC, datetime

from screencare.summary import dashboard

NOW = datetime(2026, 1, 7, 18, 0, tzinfo=UTC)


def focus(ended_at: str, active_s: int, outcome: str = "completed") -> dict:
    return {"type": "focus", "ended_at": ended_at, "active_s": active_s, "outcome": outcome}


def test_empty_history_is_all_zeros():
    result = dashboard([], NOW)
    assert set(result["today"].values()) == {0}
    assert len(result["trend"]) == 7
    assert result["trend"][-1]["date"] == "2026-01-07"


def test_counts_today_and_week():
    records = [
        focus("2026-01-07T10:00:00+00:00", 25 * 60),
        focus("2026-01-07T11:00:00+00:00", 50 * 60),
        focus("2026-01-07T12:00:00+00:00", 5 * 60, outcome="abandoned"),
        focus("2026-01-03T10:00:00+00:00", 25 * 60),
        focus("2025-12-01T10:00:00+00:00", 25 * 60),  # outside the window
        {"type": "break", "kind": "recovery", "ended_at": "2026-01-07T10:05:00+00:00"},
        {"type": "break", "kind": "skipped", "ended_at": "2026-01-07T11:00:00+00:00"},
        {"type": "break", "kind": "away", "seconds": 600, "ended_at": "2026-01-07T13:00:00+00:00"},
        {"type": "drink", "at": "2026-01-07T09:00:00+00:00"},
    ]
    result = dashboard(records, NOW)
    today = result["today"]
    assert today["sessions"] == 2
    assert today["focus_minutes"] == 80
    assert today["longest_session_minutes"] == 50
    assert (today["breaks_taken"], today["breaks_skipped"], today["walks"]) == (2, 1, 1)
    assert today["away_minutes"] == 10
    assert today["drinks"] == 1
    assert result["week"]["sessions"] == 3


def test_days_follow_the_users_timezone():
    late_evening_utc_minus_5 = focus("2026-01-08T03:00:00+00:00", 25 * 60)
    result = dashboard([late_evening_utc_minus_5], NOW, tz_offset_minutes=-300)
    assert result["today"]["sessions"] == 1


def test_malformed_records_are_skipped():
    result = dashboard([{"type": "focus", "ended_at": "not a date"}, {"type": "drink"}], NOW)
    assert result["today"]["sessions"] == 0
