"""Small, explicit SQL migrations. No ORM
(``ScreenCare — Implementation Standards.md`` section 11) — each migration
is a plain function that runs fixed DDL against a ``sqlite3.Connection``,
recorded in ``schema_migrations`` so it only ever runs once.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from screencare.scheduler.clock import Clock

Migration = Callable[[sqlite3.Connection], None]


def _migration_001_initial(conn: sqlite3.Connection) -> None:
    """``ScreenCare — Technical.md`` section 21's schema, minus
    ``symptom_checkins`` — the spec itself says to keep that optional and
    disabled unless the feature is actually built, so it isn't created
    until a later migration does so alongside the feature."""
    conn.execute(
        """
        CREATE TABLE focus_sessions (
            id TEXT PRIMARY KEY,
            mode TEXT NOT NULL,
            task_label TEXT,
            started_at_utc TEXT NOT NULL,
            ended_at_utc TEXT,
            planned_seconds INTEGER NOT NULL,
            active_seconds INTEGER NOT NULL DEFAULT 0,
            extension_seconds INTEGER NOT NULL DEFAULT 0,
            outcome TEXT,
            feedback TEXT,
            created_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX idx_focus_started ON focus_sessions(started_at_utc)")

    conn.execute(
        """
        CREATE TABLE break_sessions (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            started_at_utc TEXT NOT NULL,
            ended_at_utc TEXT,
            away_seconds INTEGER NOT NULL DEFAULT 0,
            completion_source TEXT,
            created_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX idx_break_started ON break_sessions(started_at_utc)")

    conn.execute(
        """
        CREATE TABLE hydration_events (
            id TEXT PRIMARY KEY,
            occurred_at_utc TEXT NOT NULL,
            action TEXT NOT NULL,
            source TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX idx_hydration_time ON hydration_events(occurred_at_utc)")

    conn.execute(
        """
        CREATE TABLE active_session_snapshot (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            mode TEXT NOT NULL,
            task_label TEXT,
            started_at_utc TEXT NOT NULL,
            planned_seconds INTEGER NOT NULL,
            active_seconds INTEGER NOT NULL,
            last_checkpoint_utc TEXT NOT NULL
        )
        """
    )


def _migration_002_idea_walk_notes(conn: sqlite3.Connection) -> None:
    """``ScreenCare — Concept.md``, "Idea Walk": a small text box to capture
    a thought on return, stored locally. Its own table (rather than folding
    into ``focus_sessions``) since a note isn't tied to any one focus
    session and note capture can be disabled independently of everything
    else (``Technical.md`` section 15)."""
    conn.execute(
        """
        CREATE TABLE idea_walk_notes (
            id TEXT PRIMARY KEY,
            occurred_at_utc TEXT NOT NULL,
            note TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX idx_idea_walk_notes_time ON idea_walk_notes(occurred_at_utc)")


# (version, description, migration). Append-only: never edit or remove a
# past entry, only add new ones — ScreenCare — Technical.md section 39.
MIGRATIONS: tuple[tuple[int, str, Migration], ...] = (
    (1, "initial schema", _migration_001_initial),
    (2, "idea walk notes", _migration_002_idea_walk_notes),
)


def apply_pending(conn: sqlite3.Connection, clock: Clock) -> list[int]:
    """Apply every migration not yet recorded in ``schema_migrations``, in
    order, each in its own transaction. Returns the versions newly
    applied. Safe to call on every startup — an up-to-date database
    applies nothing."""
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at_utc TEXT NOT NULL
            )
            """
        )
    already_applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}

    newly_applied: list[int] = []
    for version, _description, migration in MIGRATIONS:
        if version in already_applied:
            continue
        with conn:
            migration(conn)
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at_utc) VALUES (?, ?)",
                (version, clock.utc_now().isoformat()),
            )
        newly_applied.append(version)
    return newly_applied
