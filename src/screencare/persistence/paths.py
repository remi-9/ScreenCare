"""Resolves the OS-correct location for ScreenCare's database file.

Needs PySide6 (``QStandardPaths``) — one of only two modules in
``persistence`` that do (the other is
:class:`~screencare.persistence.settings.QSettingsBackend`). Everything
else here is plain Python, tested against a real (temporary) or
in-memory SQLite database. Never place files directly under the user's
home folder — ``ScreenCare — Implementation Standards.md`` section 10.
"""

from __future__ import annotations

from pathlib import Path


def default_database_path() -> Path:
    from PySide6.QtCore import QStandardPaths

    location = QStandardPaths.StandardLocation.AppLocalDataLocation
    base = QStandardPaths.writableLocation(location)
    return Path(base) / "screencare.sqlite3"
