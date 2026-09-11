"""Local storage: SQLite history + migrations, the crash-recovery session
snapshot, and validated ``QSettings``-backed preferences.

Everything except ``paths.py`` (needs ``QStandardPaths``) and the
``QSettingsBackend`` class in ``settings.py`` (needs ``QSettings``) is
plain Python, tested against a real or in-memory SQLite connection.
"""
