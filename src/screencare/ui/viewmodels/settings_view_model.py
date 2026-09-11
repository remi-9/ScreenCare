"""``SettingsViewModel``: QML bindings over :class:`~screencare.persistence.settings.AppSettings`.

Every setter goes through ``AppSettings`` (which clamps to the bounds in
``ScreenCare — Implementation Standards.md`` section 30) and then calls
``on_settings_changed`` so already-running countdowns
(:class:`~screencare.engines.hydration_engine.HydrationEngine`,
:class:`~screencare.engines.eye_rest_engine.EyeRestEngine`) pick up the new
value on their *next* interval rather than retroactively — see
:meth:`~screencare.app.session.AppSession.apply_settings_changed`. Never
trusts a value QML sends without going through ``AppSettings`` first
(``Technical.md`` section 30: "Never trust QML input values directly.").
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Property, QObject, Signal, Slot

from screencare.persistence.settings import AppSettings


class SettingsViewModel(QObject):
    changed = Signal()

    def __init__(
        self,
        settings: AppSettings,
        on_settings_changed: Callable[[], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._on_settings_changed = on_settings_changed or (lambda: None)

    def _commit(self) -> None:
        self._settings.sync()
        self._on_settings_changed()
        self.changed.emit()

    # -- focus / breaks ---------------------------------------------------------

    @Property(int, notify=changed)
    def focusMinutes(self) -> int:
        return self._settings.focus_minutes

    @focusMinutes.setter
    def focusMinutes(self, value: int) -> None:
        self._settings.focus_minutes = value
        self._commit()

    @Property(int, notify=changed)
    def shortBreakMinutes(self) -> int:
        return self._settings.short_break_minutes

    @shortBreakMinutes.setter
    def shortBreakMinutes(self, value: int) -> None:
        self._settings.short_break_minutes = value
        self._commit()

    # -- hydration ----------------------------------------------------------------

    @Property(int, notify=changed)
    def hydrationIntervalMinutes(self) -> int:
        return self._settings.hydration_interval_minutes

    @hydrationIntervalMinutes.setter
    def hydrationIntervalMinutes(self, value: int) -> None:
        self._settings.hydration_interval_minutes = value
        self._commit()

    @Property(bool, notify=changed)
    def hydrationStrict(self) -> bool:
        return self._settings.hydration_strict

    @hydrationStrict.setter
    def hydrationStrict(self, value: bool) -> None:
        self._settings.hydration_strict = value
        self._commit()

    # -- eye rest -------------------------------------------------------------------

    @Property(int, notify=changed)
    def eyeReminderMinutes(self) -> int:
        return self._settings.eye_reminder_minutes

    @eyeReminderMinutes.setter
    def eyeReminderMinutes(self, value: int) -> None:
        self._settings.eye_reminder_minutes = value
        self._commit()

    @Property(bool, notify=changed)
    def eyeReminderEnabled(self) -> bool:
        return self._settings.eye_reminder_enabled

    @eyeReminderEnabled.setter
    def eyeReminderEnabled(self, value: bool) -> None:
        self._settings.eye_reminder_enabled = value
        self._commit()

    # -- notifications / app-level ---------------------------------------------------

    @Property(int, notify=changed)
    def quietModeMinutes(self) -> int:
        return self._settings.quiet_mode_minutes

    @quietModeMinutes.setter
    def quietModeMinutes(self, value: int) -> None:
        self._settings.quiet_mode_minutes = value
        self._commit()

    @Property(bool, notify=changed)
    def notificationsEnabled(self) -> bool:
        return self._settings.notifications_enabled

    @notificationsEnabled.setter
    def notificationsEnabled(self, value: bool) -> None:
        self._settings.notifications_enabled = value
        self._commit()

    @Property(bool, notify=changed)
    def soundEnabled(self) -> bool:
        return self._settings.sound_enabled

    @soundEnabled.setter
    def soundEnabled(self, value: bool) -> None:
        self._settings.sound_enabled = value
        self._commit()

    @Property(bool, notify=changed)
    def launchAtLogin(self) -> bool:
        return self._settings.launch_at_login

    @launchAtLogin.setter
    def launchAtLogin(self, value: bool) -> None:
        # Only the preference is stored here; actually registering/removing
        # the OS autostart entry is Phase 5's job (a Windows platform
        # adapter) -- see ARCHITECTURE.md.
        self._settings.launch_at_login = value
        self._commit()

    @Property(str, notify=changed)
    def theme(self) -> str:
        return self._settings.theme

    @theme.setter
    def theme(self, value: str) -> None:
        if value not in ("system", "light", "dark"):
            return
        self._settings.theme = value
        self._commit()

    @Slot()
    def markOnboardingCompleted(self) -> None:
        self._settings.onboarding_completed = True
        self._commit()

    @Property(bool, notify=changed)
    def onboardingCompleted(self) -> bool:
        return self._settings.onboarding_completed
