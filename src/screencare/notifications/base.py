"""``NotificationService``: a presentation-only output channel.

``ScreenCare — Technical.md`` section 16 is explicit that notification
delivery must never become the source of application state — a break is due
because :class:`~screencare.engines.focus_engine.FocusEngine` says so and
that gets persisted regardless of whether any notification actually reaches
the screen. Every concrete backend (this module's :class:`InMemoryNotificationService`
for tests, :class:`~screencare.notifications.tray_service.TrayNotificationService`
for the real app) is therefore purely additive: removing it must never change
what the app *knows*, only what the user *sees*.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from screencare.domain.enums import NotificationPriority


@dataclass(frozen=True)
class Notification:
    """A single notification request. ``id`` is caller-assigned and stable
    for a given logical reminder so a later call can :meth:`NotificationService.withdraw`
    it (e.g. if the state it described has since changed)."""

    id: str
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.P2_NORMAL


class NotificationService(Protocol):
    def send(self, notification: Notification) -> None: ...

    def withdraw(self, notification_id: str) -> None: ...


class InMemoryNotificationService:
    """Records notifications instead of displaying them anywhere.

    Used by tests (so :class:`~screencare.app.session.AppSession` is fully
    testable without Qt) and doubles as the safe default the app falls back
    to if no tray/OS notification path is available — internal state stays
    correct either way, exactly as ``Technical.md`` section 41 requires
    ("Notification unavailable: keep internal state correct")."""

    def __init__(self) -> None:
        self.sent: list[Notification] = []
        self.withdrawn: list[str] = []

    def send(self, notification: Notification) -> None:
        self.sent.append(notification)

    def withdraw(self, notification_id: str) -> None:
        self.withdrawn.append(notification_id)

    @property
    def last(self) -> Notification | None:
        return self.sent[-1] if self.sent else None
