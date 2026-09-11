"""The SQLite connection: pragmas, migrations, and one exception type so
callers can handle a broken database deliberately instead of crash-looping
(``ScreenCare — Implementation Standards.md`` section 41).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from screencare.persistence.migrations import apply_pending
from screencare.scheduler.clock import Clock

# ScreenCare — Technical.md section 20.
_PRAGMAS = (
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA foreign_keys = ON",
    "PRAGMA busy_timeout = 3000",
)


class DatabaseError(RuntimeError):
    """Wraps every error raised while opening or migrating the database
    (filesystem or sqlite3) so callers only need to handle one type."""


class Database:
    """A thin wrapper around one ``sqlite3.Connection``: applies the
    required pragmas and brings the schema up to date. Repositories own
    the actual queries — this class is just a connection holder."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    @classmethod
    def open(cls, path: Path, *, clock: Clock) -> Database:
        """Open (creating if needed) the database file at ``path``."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(str(path))
            return cls._configure(connection, clock)
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseError(f"could not open database at {path}: {exc}") from exc

    @classmethod
    def open_in_memory(cls, *, clock: Clock) -> Database:
        """An in-memory database — same schema, no file on disk. Used by
        tests. Note SQLite ignores ``journal_mode=WAL`` for ``:memory:``
        databases (there's no file to journal against); that's fine, WAL
        is a durability/concurrency property of the real file, not
        something any test depends on."""
        try:
            connection = sqlite3.connect(":memory:")
            return cls._configure(connection, clock)
        except sqlite3.Error as exc:
            raise DatabaseError(f"could not open in-memory database: {exc}") from exc

    @classmethod
    def _configure(cls, connection: sqlite3.Connection, clock: Clock) -> Database:
        connection.row_factory = sqlite3.Row
        for pragma in _PRAGMAS:
            connection.execute(pragma)
        apply_pending(connection, clock)
        return cls(connection)

    def close(self) -> None:
        self.connection.close()
