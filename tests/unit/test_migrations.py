import sqlite3

from screencare.persistence.migrations import apply_pending
from screencare.scheduler.clock import FakeClock


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row[0] for row in rows}


def test_apply_pending_creates_the_expected_tables() -> None:
    conn = sqlite3.connect(":memory:")
    apply_pending(conn, FakeClock())
    tables = _tables(conn)
    assert {
        "schema_migrations",
        "focus_sessions",
        "break_sessions",
        "hydration_events",
        "active_session_snapshot",
        "idea_walk_notes",
    } <= tables


def test_apply_pending_records_the_applied_versions() -> None:
    conn = sqlite3.connect(":memory:")
    clock = FakeClock()
    newly_applied = apply_pending(conn, clock)
    assert newly_applied == [1, 2]

    rows = conn.execute(
        "SELECT version, applied_at_utc FROM schema_migrations ORDER BY version"
    ).fetchall()
    assert [row[0] for row in rows] == [1, 2]
    assert rows[0][1] == clock.utc_now().isoformat()


def test_apply_pending_is_idempotent() -> None:
    conn = sqlite3.connect(":memory:")
    clock = FakeClock()
    apply_pending(conn, clock)

    clock.advance(minutes=5)
    newly_applied = apply_pending(conn, clock)
    assert newly_applied == []  # already up to date — no error, no re-creation
