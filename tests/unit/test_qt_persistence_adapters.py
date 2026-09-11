"""The two persistence pieces that need PySide6 rather than being plain
Python: the QStandardPaths-based default database path, and the QSettings
backend. Skipped automatically if PySide6 isn't installed (same pattern as
``tests/ui/test_bootstrap_qml.py``), but runs for real wherever it is.

Every ``QSettingsBackend`` here is built on an explicit, temp-file-backed
``QSettings`` — never the app-wide default — so running these tests never
reads or writes the developer's real, persistent ScreenCare settings.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QSettings  # noqa: E402

from screencare.persistence.paths import default_database_path  # noqa: E402
from screencare.persistence.settings import AppSettings, QSettingsBackend  # noqa: E402


@pytest.fixture(autouse=True)
def _app_identity():
    # QStandardPaths needs an application/organization name to resolve a
    # real per-app location. A QCoreApplication is enough (no display
    # needed) and app/bootstrap.py sets the same names for the real app.
    if QCoreApplication.instance() is None:
        app = QCoreApplication([])
        app.setOrganizationName("Pivotly")
        app.setApplicationName("ScreenCare")
    yield


def _isolated_backend(tmp_path) -> QSettingsBackend:
    ini_path = tmp_path / "test_settings.ini"
    return QSettingsBackend(QSettings(str(ini_path), QSettings.Format.IniFormat))


def test_default_database_path_is_under_a_screencare_named_location() -> None:
    path = default_database_path()
    assert path.name == "screencare.sqlite3"
    assert "screencare" in str(path).lower()


def test_qsettings_backend_round_trips_a_value(tmp_path) -> None:
    backend = _isolated_backend(tmp_path)
    backend.set_value("test/round_trip", "hello")
    assert backend.value("test/round_trip", None) == "hello"
    backend.sync()


def test_app_settings_works_over_the_real_qsettings_backend(tmp_path) -> None:
    settings = AppSettings(_isolated_backend(tmp_path))
    settings.focus_minutes = 33
    assert settings.focus_minutes == 33
