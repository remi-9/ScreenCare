import pytest

from screencare.persistence.database import Database, DatabaseError
from screencare.scheduler.clock import FakeClock


def test_open_in_memory_applies_pragmas_and_migrations() -> None:
    db = Database.open_in_memory(clock=FakeClock())
    try:
        assert db.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.connection.execute("PRAGMA synchronous").fetchone()[0] == 1  # NORMAL
        tables = {
            row[0]
            for row in db.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert "focus_sessions" in tables
    finally:
        db.close()


def test_open_creates_a_real_file_and_parent_directories(tmp_path) -> None:
    path = tmp_path / "nested" / "screencare.sqlite3"
    db = Database.open(path, clock=FakeClock())
    try:
        assert path.is_file()
        assert db.connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        db.close()


def test_reopening_an_existing_database_does_not_recreate_tables(tmp_path) -> None:
    path = tmp_path / "screencare.sqlite3"
    clock = FakeClock()
    db1 = Database.open(path, clock=clock)
    db1.connection.execute(
        "INSERT INTO hydration_events (id, occurred_at_utc, action, source) "
        "VALUES ('a', '2026-01-01T00:00:00+00:00', 'logged', 'manual')"
    )
    db1.connection.commit()
    db1.close()

    clock.advance(minutes=1)
    db2 = Database.open(path, clock=clock)
    try:
        count = db2.connection.execute("SELECT COUNT(*) FROM hydration_events").fetchone()[0]
        assert count == 1  # data survived; migration wasn't re-run destructively
    finally:
        db2.close()


def test_open_wraps_filesystem_errors_as_database_error(tmp_path) -> None:
    # Make a regular file stand where a directory needs to be created,
    # so mkdir() fails with a filesystem error rather than a sqlite3 one.
    blocking_file = tmp_path / "not_a_directory"
    blocking_file.write_text("x")
    bad_path = blocking_file / "screencare.sqlite3"

    with pytest.raises(DatabaseError):
        Database.open(bad_path, clock=FakeClock())


def test_open_wraps_sqlite_errors_as_database_error(tmp_path) -> None:
    # An empty file that isn't a valid SQLite database triggers a genuine
    # sqlite3.DatabaseError once a statement is executed against it.
    path = tmp_path / "corrupt.sqlite3"
    path.write_bytes(b"not a sqlite database")

    with pytest.raises(DatabaseError):
        Database.open(path, clock=FakeClock())
