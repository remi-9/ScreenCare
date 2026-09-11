"""Combines competing reminders into one intervention instead of several.

Phase 2 scope: pure decision logic over "seconds until due" inputs supplied
by the caller. It does not own scheduling or notification delivery — those
are :class:`~screencare.scheduler.scheduler.Scheduler`'s and (Phase 4's)
``NotificationService``'s jobs respectively. See
``ScreenCare — Technical.md`` section 7 and section 9.
"""

from __future__ import annotations

from dataclasses import dataclass

from screencare.engines.hydration_engine import HydrationSettings


@dataclass(frozen=True)
class RecoveryDecision:
    """What a single recovery-break intervention should include."""

    fire_in_seconds: float
    include_hydration: bool
    include_eye_rest: bool


class WellnessCoordinator:
    def __init__(self, hydration_settings: HydrationSettings | None = None) -> None:
        self._hydration_settings = hydration_settings or HydrationSettings()

    def decide_recovery(
        self,
        *,
        recovery_due_in_seconds: float,
        hydration_due_in_seconds: float | None,
        eye_rest_overdue: bool,
    ) -> RecoveryDecision:
        """Decide what the upcoming recovery break should include.

        Mirrors the worked example in ``ScreenCare — Technical.md``
        section 7: if hydration is due within the merge window *ahead of*
        the recovery break, fold it into that break instead of firing a
        separate reminder first. In strict hydration mode, never merge —
        section 9's "Strict hourly hydration reminders" setting means
        hydration always fires at exactly its own due time.
        """
        include_hydration = False
        if hydration_due_in_seconds is not None and not self._hydration_settings.strict:
            gap = recovery_due_in_seconds - hydration_due_in_seconds
            if 0 <= gap <= self._hydration_settings.merge_window_seconds:
                include_hydration = True
        return RecoveryDecision(
            fire_in_seconds=recovery_due_in_seconds,
            include_hydration=include_hydration,
            include_eye_rest=eye_rest_overdue,
        )

    def should_fire_hydration_standalone(
        self,
        *,
        hydration_due_in_seconds: float,
        recovery_due_in_seconds: float | None,
    ) -> bool:
        """Whether hydration should notify on its own, right now.

        True once hydration is actually due (``<= 0``) *and* there is no
        recovery break close enough to fold it into instead (that case is
        handled by :meth:`decide_recovery`, so raising this notification
        too would duplicate it).
        """
        if hydration_due_in_seconds > 0:
            return False
        if self._hydration_settings.strict or recovery_due_in_seconds is None:
            return True
        gap = recovery_due_in_seconds - hydration_due_in_seconds
        return not (0 <= gap <= self._hydration_settings.merge_window_seconds)
