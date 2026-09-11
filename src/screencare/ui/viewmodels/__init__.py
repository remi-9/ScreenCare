"""Narrow view models exposed to QML: ``FocusViewModel``, ``BreakViewModel``,
``SettingsViewModel``, ``DashboardViewModel`` (``ScreenCare — Technical.md``
section 24). Every one of them wraps something narrower than "the whole
app" -- ``AppSession`` for the first two, ``AppSettings`` for the third, the
history repositories directly for the read-only fourth. QML is never given
direct access to the database or the coordinator.
"""
