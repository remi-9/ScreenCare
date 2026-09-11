"""NotificationService: a presentation-only output channel for reminders.

``base.py`` defines the ``NotificationService`` protocol plus
``InMemoryNotificationService`` (Qt-free — used by tests and as the
"nothing available" fallback). ``tray_service.py`` adds
``TrayNotificationService``, a thin ``QSystemTrayIcon`` adapter built by
``app/bootstrap.py``. Notification delivery must never become the source of
application state (``ScreenCare — Technical.md``, section 16) — every
backend here is purely additive to what
:class:`~screencare.app.session.AppSession` already decided and persisted.
"""
