"""Explicit SQL repositories — one per table, no ORM
(``ScreenCare — Implementation Standards.md`` section 11). Each write is
its own short transaction; nothing here holds a connection open across an
unrelated unit of work.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from screencare.domain.enums import (
    BreakCompletionSource,
    BreakKind,
    FocusFeedback,
    FocusMode,
    FocusOutcome,
)
from screencare.domain.models import BreakSession, FocusSessionSummary, HydrationEvent
from screencare.scheduler.clock import Clock


class FocusSessionRepository:
    def __init__(self, connection: sqlite3.Connection, clock: Clock) -> None:
        self._connection = connection
        self._clock = clock

    def insert(self, summary: FocusSessionSummary) -> str:
        """Persist a concluded focus session. Returns the generated row id."""
        row_id = str(uuid.uuid4())
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO focus_sessions (
                    id, mode, task_label, started_at_utc, ended_at_utc,
                    planned_seconds, active_seconds, extension_seconds,
                    outcome, feedback, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    summary.mode.value,
                    summary.task_label,
                    summary.started_at_utc.isoformat(),
                    summary.ended_at_utc.isoformat(),
                    summary.planned_seconds,
                    summary.active_seconds,
                    summary.extension_seconds,
                    summary.outcome.value,
                    summary.feedback.value if summary.feedback else None,
                    self._clock.utc_now().isoformat(),
                ),
            )
        return row_id

    def list_recent(self, limit: int = 50) -> list[FocusSessionSummary]:
        rows = self._connection.execute(
            "SELECT * FROM focus_sessions ORDER BY started_at_utc DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_focus_summary(row) for row in rows]


def _row_to_focus_summary(row: sqlite3.Row) -> FocusSessionSummary:
    return FocusSessionSummary(
        mode=FocusMode(row["mode"]),
        task_label=row["task_label"],
        started_at_utc=datetime.fromisoformat(row["started_at_utc"]),
        ended_at_utc=datetime.fromisoformat(row["ended_at_utc"]),
        planned_seconds=row["planned_seconds"],
        active_seconds=row["active_seconds"],
        extension_seconds=row["extension_seconds"],
        outcome=FocusOutcome(row["outcome"]),
        feedback=FocusFeedback(row["feedback"]) if row["feedback"] else None,
    )


class BreakSessionRepository:
    def __init__(self, connection: sqlite3.Connection, clock: Clock) -> None:
        self._connection = connection
        self._clock = clock

    def insert(self, session: BreakSession) -> str:
        if session.ended_at_utc is None:
            raise ValueError("cannot persist a break session that hasn't ended")
        row_id = str(uuid.uuid4())
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO break_sessions (
                    id, kind, started_at_utc, ended_at_utc, away_seconds,
                    completion_source, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    session.kind.value,
                    session.started_at_utc.isoformat(),
                    session.ended_at_utc.isoformat(),
                    session.away_seconds,
                    session.completion_source.value if session.completion_source else None,
                    self._clock.utc_now().isoformat(),
                ),
            )
        return row_id

    def list_recent(self, limit: int = 50) -> list[BreakSession]:
        rows = self._connection.execute(
            "SELECT * FROM break_sessions ORDER BY started_at_utc DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_break_session(row) for row in rows]


def _row_to_break_session(row: sqlite3.Row) -> BreakSession:
    return BreakSession(
        kind=BreakKind(row["kind"]),
        started_at_utc=datetime.fromisoformat(row["started_at_utc"]),
        ended_at_utc=datetime.fromisoformat(row["ended_at_utc"]),
        away_seconds=row["away_seconds"],
        completion_source=(
            BreakCompletionSource(row["completion_source"]) if row["completion_source"] else None
        ),
    )


class HydrationEventRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def insert(self, event: HydrationEvent) -> str:
        row_id = str(uuid.uuid4())
        with self._connection:
            self._connection.execute(
                "INSERT INTO hydration_events (id, occurred_at_utc, action, source) "
                "VALUES (?, ?, ?, ?)",
                (row_id, event.occurred_at_utc.isoformat(), event.action, event.source),
            )
        return row_id

    def list_recent(self, limit: int = 50) -> list[HydrationEvent]:
        rows = self._connection.execute(
            "SELECT * FROM hydration_events ORDER BY occurred_at_utc DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            HydrationEvent(
                occurred_at_utc=datetime.fromisoformat(row["occurred_at_utc"]),
                action=row["action"],
                source=row["source"],
            )
            for row in rows
        ]
