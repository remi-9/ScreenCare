"""Dashboard numbers from the history records the browser keeps.

Small, explainable counts about patterns, not a productivity score.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from typing import Any


def _local_day(value: str | datetime, tz: timezone) -> date:
    when = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    return when.astimezone(tz).date()


def _day_stats(records: list[dict[str, Any]]) -> dict[str, int]:
    focus = [r for r in records if r.get("type") == "focus"]
    completed = [r for r in focus if r.get("outcome") == "completed"]
    breaks = [r for r in records if r.get("type") == "break"]
    taken = [b for b in breaks if b.get("kind") != "skipped"]
    active = [int(r.get("active_s", 0)) for r in focus]
    return {
        "sessions": len(completed),
        "focus_minutes": sum(active) // 60,
        "avg_session_minutes": (sum(active) // len(active)) // 60 if active else 0,
        "longest_session_minutes": max(active, default=0) // 60,
        "breaks_taken": len(taken),
        "breaks_skipped": len(breaks) - len(taken),
        "walks": sum(1 for b in taken if b.get("kind") in ("recovery", "idea_walk")),
        "away_minutes": sum(int(b.get("seconds", 0)) for b in breaks if b.get("kind") == "away")
        // 60,
        "drinks": sum(1 for r in records if r.get("type") == "drink"),
        "ideas": sum(1 for r in records if r.get("type") == "note"),
    }


def dashboard(
    records: Iterable[dict[str, Any]], now: datetime, tz_offset_minutes: int = 0
) -> dict[str, Any]:
    """Today's stats plus a 7-day trend, in the user's local days."""
    tz = timezone(timedelta(minutes=tz_offset_minutes))
    today = now.astimezone(tz).date()
    days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    by_day: dict[date, list[dict[str, Any]]] = {day: [] for day in days}
    for record in records:
        stamp = record.get("ended_at") or record.get("at")
        if not stamp:
            continue
        try:
            day = _local_day(stamp, tz)
        except (TypeError, ValueError):
            continue  # a malformed record shouldn't break the whole dashboard
        if day in by_day:
            by_day[day].append(record)

    week = [r for day in days for r in by_day[day]]
    return {
        "today": _day_stats(by_day[today]),
        "week": _day_stats(week),
        "trend": [
            {
                "date": day.isoformat(),
                "label": day.strftime("%a"),
                **{k: v for k, v in _day_stats(by_day[day]).items() if k in _TREND_KEYS},
            }
            for day in days
        ],
    }


_TREND_KEYS = {"focus_minutes", "breaks_taken", "sessions"}
