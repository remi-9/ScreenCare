"""``DashboardViewModel``: the one view model that reads history directly
(through the repositories, never raw SQL or the whole database) rather than
through :class:`~screencare.app.session.AppSession` — the dashboard is a
read-only report over the past, not a control surface for the live session.

Queries run only when :meth:`refresh` is called
(``ScreenCare — Technical.md`` section 42: "when the dashboard opens, after
a relevant completed event, or when the user changes the date range") —
never on the per-second UI timer.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from screencare.analytics.summary import dashboard_summary, start_of_today, start_of_week
from screencare.persistence.repositories import (
    BreakSessionRepository,
    FocusSessionRepository,
    HydrationEventRepository,
)
from screencare.scheduler.clock import Clock


class DashboardViewModel(QObject):
    changed = Signal()

    def __init__(
        self,
        *,
        clock: Clock,
        focus_repo: FocusSessionRepository,
        break_repo: BreakSessionRepository,
        hydration_repo: HydrationEventRepository,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._clock = clock
        self._focus_repo = focus_repo
        self._break_repo = break_repo
        self._hydration_repo = hydration_repo

        self._today_sessions = 0
        self._today_minutes = 0
        self._today_breaks = 0
        self._week_sessions = 0
        self._week_minutes = 0
        self._week_breaks = 0

    @Slot()
    def refresh(self) -> None:
        now = self._clock.utc_now()
        today_cutoff = start_of_today(now)
        week_cutoff = start_of_week(now)

        today = dashboard_summary(
            focus_sessions=self._focus_repo.list_since(today_cutoff),
            break_sessions=self._break_repo.list_since(today_cutoff),
            hydration_events=self._hydration_repo.list_since(today_cutoff),
        )
        week = dashboard_summary(
            focus_sessions=self._focus_repo.list_since(week_cutoff),
            break_sessions=self._break_repo.list_since(week_cutoff),
            hydration_events=self._hydration_repo.list_since(week_cutoff),
        )

        self._today_sessions = today.focus_sessions_completed
        self._today_minutes = today.focus_active_minutes
        self._today_breaks = today.breaks_taken
        self._week_sessions = week.focus_sessions_completed
        self._week_minutes = week.focus_active_minutes
        self._week_breaks = week.breaks_taken
        self.changed.emit()

    @Property(int, notify=changed)
    def todaySessionsCompleted(self) -> int:
        return self._today_sessions

    @Property(int, notify=changed)
    def todayFocusMinutes(self) -> int:
        return self._today_minutes

    @Property(int, notify=changed)
    def todayBreaksTaken(self) -> int:
        return self._today_breaks

    @Property(int, notify=changed)
    def weekSessionsCompleted(self) -> int:
        return self._week_sessions

    @Property(int, notify=changed)
    def weekFocusMinutes(self) -> int:
        return self._week_minutes

    @Property(int, notify=changed)
    def weekBreaksTaken(self) -> int:
        return self._week_breaks
