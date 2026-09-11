"""``PresenceMonitor``: turns whatever an :class:`ActivityProvider` reports
into a single :class:`~screencare.domain.enums.PresenceState`, per the
decision table in ``ScreenCare — Technical.md`` section 13:

.. code-block:: text

    idle < 90 sec     -> remain ACTIVE
    idle >= 90 sec    -> IDLE
    locked            -> LOCKED
    system sleep      -> SLEEPING

Deliberately Qt-free and platform-free -- it only depends on the
``ActivityProvider`` protocol, so it's fully unit-testable with a fake
provider, and it degrades to always-``ACTIVE`` when no provider is
available at all, or once one starts raising
(``ScreenCare — Implementation Standards.md`` section 14: "idle API
unavailable -> disable automatic away detection -> focus system continues
working normally"; ``ScreenCare — Technical.md`` section 41: "Idle API
fails -> continue focus timer, disable automatic-away detection, log
adapter failure").
"""

from __future__ import annotations

import logging

from screencare.activity.base import ActivityProvider
from screencare.domain.enums import PresenceState

logger = logging.getLogger(__name__)

# Technical.md section 13: "Recommended starting value: idle threshold: 90 seconds".
DEFAULT_IDLE_THRESHOLD_SECONDS = 90.0


class PresenceMonitor:
    def __init__(
        self,
        *,
        provider: ActivityProvider | None,
        idle_threshold_seconds: float = DEFAULT_IDLE_THRESHOLD_SECONDS,
    ) -> None:
        self._provider = provider
        self.idle_threshold_seconds = idle_threshold_seconds
        self._sleeping = False
        self._provider_failed = False

    def set_provider(self, provider: ActivityProvider | None) -> None:
        """Attach (or replace) the provider after construction -- real
        ``bootstrap.py`` only knows the Windows adapter once the QML root
        window exists, which is after ``AppSession`` itself is built.
        Clears any previous "provider failed" latch, since a freshly
        attached provider deserves a fresh chance."""
        self._provider = provider
        self._provider_failed = False

    def mark_sleeping(self) -> None:
        """The platform power monitor reported the system is suspending."""
        self._sleeping = True

    def mark_awake(self) -> None:
        """The platform power monitor reported the system resumed. Does
        *not* itself decide the resulting presence -- call :meth:`poll`
        right after, so the real idle/lock state is queried rather than
        assuming ``ACTIVE`` (Technical.md section 12: "3. Query actual
        idle state.")."""
        self._sleeping = False

    def poll(self) -> PresenceState:
        """Best-effort snapshot of the current presence. Never raises --
        a failing provider is logged once and treated as permanently
        unavailable for the rest of the run."""
        if self._sleeping:
            return PresenceState.SLEEPING
        if self._provider is None or self._provider_failed:
            return PresenceState.ACTIVE
        try:
            if self._provider.is_locked():
                return PresenceState.LOCKED
            if self._provider.idle_seconds() >= self.idle_threshold_seconds:
                return PresenceState.IDLE
            return PresenceState.ACTIVE
        except Exception:
            logger.exception("Activity provider failed; disabling automatic away detection")
            self._provider_failed = True
            return PresenceState.ACTIVE
