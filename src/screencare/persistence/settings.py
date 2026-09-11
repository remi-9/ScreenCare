"""Validated application preferences over a small key-value backend.

``ScreenCare — Implementation Standards.md`` section 30: every
user-configurable duration needs safe bounds, and the model — not QML —
must be what enforces them. :class:`AppSettings` does that; it never
trusts a raw stored value, falling back to a safe default if the value is
missing, the wrong type, or out of range.

The backend is swappable (:class:`InMemorySettingsBackend` for tests,
:class:`QSettingsBackend` for the real app) so every rule here is testable
without Qt. ``QSettingsBackend`` is the one piece that needs PySide6; it
imports it lazily so this module stays importable without it.
"""

from __future__ import annotations

from typing import Protocol


class SettingsBackend(Protocol):
    """A minimal key-value store — exactly what ``QSettings`` provides."""

    def value(self, key: str, default: object) -> object: ...

    def set_value(self, key: str, value: object) -> None: ...

    def sync(self) -> None: ...


class InMemorySettingsBackend:
    """A dict-backed :class:`SettingsBackend` for tests — no Qt, no disk."""

    def __init__(self) -> None:
        self._data: dict[str, object] = {}

    def value(self, key: str, default: object) -> object:
        return self._data.get(key, default)

    def set_value(self, key: str, value: object) -> None:
        self._data[key] = value

    def sync(self) -> None:
        pass


class QSettingsBackend:
    """Adapts Qt's ``QSettings`` to :class:`SettingsBackend`.

    With no argument, wraps the app-wide default ``QSettings()`` — which
    needs the application name/organization already set
    (``app.setOrganizationName`` / ``setApplicationName``, done in
    ``app/bootstrap.py``). Tests should instead pass an explicit,
    isolated ``QSettings`` instance (e.g. an ``IniFormat`` one pointed at
    a temp file) so they never read or write the developer's real,
    persistent app settings as a side effect.
    """

    def __init__(self, settings: object | None = None) -> None:
        if settings is None:
            from PySide6.QtCore import QSettings

            settings = QSettings()
        self._settings = settings

    def value(self, key: str, default: object) -> object:
        return self._settings.value(key, default)

    def set_value(self, key: str, value: object) -> None:
        self._settings.setValue(key, value)

    def sync(self) -> None:
        self._settings.sync()


# (minimum, maximum) minutes — ScreenCare — Implementation Standards.md §30.
_FOCUS_MINUTES_BOUNDS = (10, 120)
_SHORT_BREAK_MINUTES_BOUNDS = (1, 30)
_HYDRATION_INTERVAL_MINUTES_BOUNDS = (30, 180)
_EYE_REMINDER_MINUTES_BOUNDS = (10, 60)
_QUIET_MODE_MINUTES_BOUNDS = (15, 240)

_VALID_THEMES = ("system", "light", "dark")


class AppSettings:
    """Typed, bounds-checked accessors for the preferences
    ``ScreenCare — Technical.md`` section 19 assigns to ``QSettings``
    (window position is deferred until Phase 4 has a real window to
    remember the position of)."""

    def __init__(self, backend: SettingsBackend) -> None:
        self._backend = backend

    # -- focus / breaks --------------------------------------------------

    @property
    def focus_minutes(self) -> int:
        return self._get_minutes("focus/duration_minutes", 25, _FOCUS_MINUTES_BOUNDS)

    @focus_minutes.setter
    def focus_minutes(self, minutes: int) -> None:
        self._set_minutes("focus/duration_minutes", minutes, _FOCUS_MINUTES_BOUNDS)

    @property
    def short_break_minutes(self) -> int:
        return self._get_minutes("focus/short_break_minutes", 5, _SHORT_BREAK_MINUTES_BOUNDS)

    @short_break_minutes.setter
    def short_break_minutes(self, minutes: int) -> None:
        self._set_minutes("focus/short_break_minutes", minutes, _SHORT_BREAK_MINUTES_BOUNDS)

    # -- hydration --------------------------------------------------------

    @property
    def hydration_interval_minutes(self) -> int:
        return self._get_minutes(
            "hydration/interval_minutes", 60, _HYDRATION_INTERVAL_MINUTES_BOUNDS
        )

    @hydration_interval_minutes.setter
    def hydration_interval_minutes(self, minutes: int) -> None:
        self._set_minutes("hydration/interval_minutes", minutes, _HYDRATION_INTERVAL_MINUTES_BOUNDS)

    @property
    def hydration_strict(self) -> bool:
        """ "Strict hourly hydration reminders" — Technical.md §9."""
        return self._get_bool("hydration/strict", False)

    @hydration_strict.setter
    def hydration_strict(self, enabled: bool) -> None:
        self._backend.set_value("hydration/strict", bool(enabled))

    # -- eye rest -----------------------------------------------------------

    @property
    def eye_reminder_minutes(self) -> int:
        return self._get_minutes("eye_rest/interval_minutes", 20, _EYE_REMINDER_MINUTES_BOUNDS)

    @eye_reminder_minutes.setter
    def eye_reminder_minutes(self, minutes: int) -> None:
        self._set_minutes("eye_rest/interval_minutes", minutes, _EYE_REMINDER_MINUTES_BOUNDS)

    @property
    def eye_reminder_enabled(self) -> bool:
        return self._get_bool("eye_rest/enabled", True)

    @eye_reminder_enabled.setter
    def eye_reminder_enabled(self, enabled: bool) -> None:
        self._backend.set_value("eye_rest/enabled", bool(enabled))

    # -- quiet mode / notifications / sound ------------------------------

    @property
    def quiet_mode_minutes(self) -> int:
        return self._get_minutes("notifications/quiet_mode_minutes", 60, _QUIET_MODE_MINUTES_BOUNDS)

    @quiet_mode_minutes.setter
    def quiet_mode_minutes(self, minutes: int) -> None:
        self._set_minutes("notifications/quiet_mode_minutes", minutes, _QUIET_MODE_MINUTES_BOUNDS)

    @property
    def notifications_enabled(self) -> bool:
        return self._get_bool("notifications/enabled", True)

    @notifications_enabled.setter
    def notifications_enabled(self, enabled: bool) -> None:
        self._backend.set_value("notifications/enabled", bool(enabled))

    @property
    def sound_enabled(self) -> bool:
        return self._get_bool("notifications/sound_enabled", True)

    @sound_enabled.setter
    def sound_enabled(self, enabled: bool) -> None:
        self._backend.set_value("notifications/sound_enabled", bool(enabled))

    # -- app-level ----------------------------------------------------------

    @property
    def launch_at_login(self) -> bool:
        return self._get_bool("app/launch_at_login", False)

    @launch_at_login.setter
    def launch_at_login(self, enabled: bool) -> None:
        self._backend.set_value("app/launch_at_login", bool(enabled))

    @property
    def onboarding_completed(self) -> bool:
        return self._get_bool("app/onboarding_completed", False)

    @onboarding_completed.setter
    def onboarding_completed(self, completed: bool) -> None:
        self._backend.set_value("app/onboarding_completed", bool(completed))

    @property
    def theme(self) -> str:
        raw = self._backend.value("app/theme", "system")
        return raw if raw in _VALID_THEMES else "system"

    @theme.setter
    def theme(self, theme: str) -> None:
        if theme not in _VALID_THEMES:
            raise ValueError(f"theme must be one of {_VALID_THEMES}, got {theme!r}")
        self._backend.set_value("app/theme", theme)

    def sync(self) -> None:
        self._backend.sync()

    # -- shared bounds-checked helpers ------------------------------------

    def _get_minutes(self, key: str, default: int, bounds: tuple[int, int]) -> int:
        raw = self._backend.value(key, default)
        try:
            minutes = int(raw)
        except (TypeError, ValueError):
            minutes = default
        lo, hi = bounds
        return max(lo, min(hi, minutes))

    def _set_minutes(self, key: str, minutes: int, bounds: tuple[int, int]) -> None:
        lo, hi = bounds
        self._backend.set_value(key, max(lo, min(hi, int(minutes))))

    def _get_bool(self, key: str, default: bool) -> bool:
        raw = self._backend.value(key, default)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.strip().lower() in ("1", "true", "yes", "on")
        return bool(raw)
