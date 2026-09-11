"""Adaptive Focus: deterministic, explainable duration tuning.

No machine learning by design (``ScreenCare — Technical.md`` section 10):
the same feedback always produces the same adjustment, and this engine only
ever proposes the *next default* — it never prevents the user from picking
their own manual duration.
"""

from __future__ import annotations

from dataclasses import dataclass

from screencare.domain.enums import FocusFeedback


@dataclass(frozen=True)
class AdaptiveFocusBounds:
    minimum_seconds: int = 20 * 60
    maximum_seconds: int = 60 * 60
    step_seconds: int = 5 * 60

    def __post_init__(self) -> None:
        if self.minimum_seconds <= 0 or self.maximum_seconds <= 0 or self.step_seconds <= 0:
            raise ValueError("AdaptiveFocusBounds values must be positive")
        if self.minimum_seconds > self.maximum_seconds:
            raise ValueError("minimum_seconds must not exceed maximum_seconds")


class AdaptiveFocusEngine:
    def __init__(
        self,
        *,
        initial_seconds: int = 25 * 60,
        bounds: AdaptiveFocusBounds | None = None,
    ) -> None:
        self._bounds = bounds or AdaptiveFocusBounds()
        self._current_seconds = self._clamp(initial_seconds)

    @property
    def current_duration_seconds(self) -> int:
        return self._current_seconds

    def record_outcome(self, *, feedback: FocusFeedback, completion_rate: float) -> int:
        """Adjust and return the new recommended focus duration, in
        seconds, given feedback on the session that just ended.

        ``completion_rate`` is ``active_seconds / planned_seconds`` for
        that session (see
        :attr:`screencare.domain.models.FocusSessionSummary.completion_rate`).

        Mirrors ``ScreenCare — Technical.md`` section 10 exactly:

        >>> if feedback == "too_short" and completion_rate > 0.8:
        ...     next_duration += 5 * 60
        >>> elif feedback == "too_long":
        ...     next_duration -= 5 * 60
        """
        if feedback is FocusFeedback.TOO_SHORT and completion_rate > 0.8:
            self._current_seconds = self._clamp(self._current_seconds + self._bounds.step_seconds)
        elif feedback is FocusFeedback.TOO_LONG:
            self._current_seconds = self._clamp(self._current_seconds - self._bounds.step_seconds)
        # JUST_RIGHT, or TOO_SHORT with a low completion rate, is left
        # unchanged: a session abandoned early doesn't mean it was too
        # short, so it must not push the duration up.
        return self._current_seconds

    def _clamp(self, seconds: int) -> int:
        return max(self._bounds.minimum_seconds, min(self._bounds.maximum_seconds, seconds))
