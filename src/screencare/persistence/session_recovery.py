"""Crash-recovery snapshot of an in-progress focus session, and the pure
reconciliation rule applied on the next startup.

``ScreenCare — Technical.md`` section 23 /
``ScreenCare — Implementation Standards.md`` section 26: never invent
completed work. A restart shortly after a crash offers to resume; a
longer gap just closes the session as interrupted; either way the
decision comes from timestamps, not guesses. This is specifically about
surviving an unexpected process exit — the *live*, in-process sleep/idle
handling during a session that's still running is
:meth:`~screencare.engines.focus_engine.FocusEngine.on_presence_changed`'s
job (Phase 2), not this module's.

Wiring — actually calling :meth:`SessionSnapshotRepository.save` from a
running session at "at most once a minute plus every transition" per
``ScreenCare — Technical.md`` section 22 — is Phase 4's job, once a real
event loop exists to drive that cadence. This module only provides the
storage and the reconciliation rule, both fully testable without one.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from screencare.domain.enums import FocusMode

# "restart within ~2 minutes -> offer Resume Session" — Technical.md §23.
RESUME_WINDOW_SECONDS = 120


@dataclass(frozen=True)
class SessionSnapshot:
    """The minimum needed to reconstruct an in-progress session after an
    unexpected restart. ``active_seconds``/``last_checkpoint_utc`` are as
    of the last time this was saved, not necessarily up to the moment of
    the crash."""

    mode: FocusMode
    task_label: str | None
    started_at_utc: datetime
    planned_seconds: int
    active_seconds: int
    last_checkpoint_utc: datetime


class RecoveryAction(StrEnum):
    NONE = "none"
    RESUME_OFFERED = "resume_offered"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class RecoveryOutcome:
    action: RecoveryAction
    snapshot: SessionSnapshot | None
    gap_seconds: float | None


def reconcile_startup_snapshot(
    snapshot: SessionSnapshot | None, now_utc: datetime
) -> RecoveryOutcome:
    """Decide what to do with a snapshot found on startup.

    No snapshot -> nothing to reconcile. Otherwise: a short gap since the
    last checkpoint offers to resume; a longer one closes the session as
    interrupted (see :data:`RESUME_WINDOW_SECONDS`). This never returns an
    outcome that claims the session *completed* — that would be inventing
    work that was never observed.
    """
    if snapshot is None:
        return RecoveryOutcome(action=RecoveryAction.NONE, snapshot=None, gap_seconds=None)
    gap = max(0.0, (now_utc - snapshot.last_checkpoint_utc).total_seconds())
    action = (
        RecoveryAction.RESUME_OFFERED
        if gap <= RESUME_WINDOW_SECONDS
        else RecoveryAction.INTERRUPTED
    )
    return RecoveryOutcome(action=action, snapshot=snapshot, gap_seconds=gap)


class SessionSnapshotRepository:
    """Persists at most one in-progress session snapshot at a time — a
    fresh :meth:`save` replaces whatever was there."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def save(self, snapshot: SessionSnapshot) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO active_session_snapshot (
                    id, mode, task_label, started_at_utc, planned_seconds,
                    active_seconds, last_checkpoint_utc
                ) VALUES (1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    mode = excluded.mode,
                    task_label = excluded.task_label,
                    started_at_utc = excluded.started_at_utc,
                    planned_seconds = excluded.planned_seconds,
                    active_seconds = excluded.active_seconds,
                    last_checkpoint_utc = excluded.last_checkpoint_utc
                """,
                (
                    snapshot.mode.value,
                    snapshot.task_label,
                    snapshot.started_at_utc.isoformat(),
                    snapshot.planned_seconds,
                    snapshot.active_seconds,
                    snapshot.last_checkpoint_utc.isoformat(),
                ),
            )

    def load(self) -> SessionSnapshot | None:
        row = self._connection.execute(
            "SELECT * FROM active_session_snapshot WHERE id = 1"
        ).fetchone()
        if row is None:
            return None
        return SessionSnapshot(
            mode=FocusMode(row["mode"]),
            task_label=row["task_label"],
            started_at_utc=datetime.fromisoformat(row["started_at_utc"]),
            planned_seconds=row["planned_seconds"],
            active_seconds=row["active_seconds"],
            last_checkpoint_utc=datetime.fromisoformat(row["last_checkpoint_utc"]),
        )

    def clear(self) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM active_session_snapshot WHERE id = 1")
