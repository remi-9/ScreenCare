"""``NotificationService`` backed by ``QSystemTrayIcon`` — the MVP delivery
mechanism ``ScreenCare — Technical.md`` section 16 specifies.

Qt documents that OS/user configuration can prevent a tray balloon/toast
from actually appearing, and section 41 requires the app to "keep internal
state correct" and "show notification inside app when visible" regardless.
This class therefore never has veto power over anything: it is constructed
after :class:`~screencare.app.session.AppSession` has already decided and
persisted what happened, and it only ever *attempts* to also put a message
on screen. The last thing it attempted is kept on :attr:`last_message` so a
QML view can show a lightweight in-app equivalent whenever the OS balloon
itself may not have been shown (unsupported platform, suppressed by the
user, or no tray icon at all).
"""

from __future__ import annotations

import logging

from screencare.notifications.base import Notification

logger = logging.getLogger(__name__)

# QSystemTrayIcon.MessageIcon has no dedicated "reminder" icon; Information
# reads as calm/non-alarming for every ScreenCare notification, which suits
# a wellness app better than Warning/Critical (Implementation Standards.md
# section 27: "calm, minimal, non-clinical").
_BALLOON_TIMEOUT_MS = 8_000


class TrayNotificationService:
    """Wraps a ``QSystemTrayIcon`` that the caller (``app/bootstrap.py``)
    already created and shown. Never constructs its own tray icon, so it has
    no opinion on the icon image, the context menu, or ``isSystemTrayAvailable()``
    — that capability check happens once at startup, in bootstrap, since it
    also decides whether a tray icon exists at all (Technical.md section 41:
    "Tray unavailable -> keep main window available")."""

    def __init__(self, tray_icon: object) -> None:
        self._tray_icon = tray_icon
        self._supports_messages = bool(getattr(tray_icon, "supportsMessages", lambda: False)())
        self.last_message: Notification | None = None

    def send(self, notification: Notification) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon

        self.last_message = notification
        if not self._supports_messages:
            logger.info("Tray messages unsupported; showing in-app only: %s", notification.id)
            return
        try:
            self._tray_icon.showMessage(
                notification.title,
                notification.message,
                QSystemTrayIcon.MessageIcon.Information,
                _BALLOON_TIMEOUT_MS,
            )
        except Exception:  # pragma: no cover - defensive; never let this crash the app
            logger.exception("Failed to show tray notification %s", notification.id)

    def withdraw(self, notification_id: str) -> None:
        # QSystemTrayIcon has no per-message withdraw; clearing the
        # in-app-visible copy is all that's meaningful here.
        if self.last_message is not None and self.last_message.id == notification_id:
            self.last_message = None
