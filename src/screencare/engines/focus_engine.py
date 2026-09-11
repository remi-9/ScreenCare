"""The focus state machine (``ScreenCare — Technical.md`` section 6).

Presence (ACTIVE/IDLE/LOCKED/SLEEPING) is orthogonal to this state machine
and doesn't exist as a real signal until Phase 5 — callers (tests today,
the activity monitor later) drive it through :meth:`FocusEngine.on_presence_changed`.
While presence is non-``ACTIVE``, active time simply stops accruing and the
focus deadline freezes; the visible :class:`FocusState` is untouched. This
is what makes the Phase 1 acceptance scenario in
``ScreenCare — Technical.md`` section 47 ("sleep 30 minutes mid-session")
correct: the session doesn't advance or complete during that gap, and no
notification burst follows it.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from screencare.domain.enums import FocusOutcome, FocusState, PresenceState
from screencare.domain.errors import InvalidStateTransition
from screencare.domain.models import FocusPlan, FocusSessionSummary
from screencare.scheduler.clock import Clock
from screencare.scheduler.deadline_budget import DeadlineBudget
from screencare.scheduler.scheduler import Scheduler

_FOCUS_KEY = "focus_deadline"
_IDEA_WALK_KEY = "idea_walk_deadline"

# "Extensions should be limited so that 'just five more minutes' cannot
# accidentally become several hours" — ScreenCare — Concept.md, "Flow
# Protection". These are conservative starting defaults, not something the
# spec pins to an exact number; callers may override them per instance.
DEFAULT_MAX_EXTENSIONS = 2
DEFAULT_EXTENSION_SECONDS = 5 * 60
DEFAULT_FINISH_THOUGHT_SECONDS = 2 * 60
DEFAULT_IDEA_WALK_SECONDS = 5 * 60  # ScreenCare — Technical.md section 15


class FocusEngine:
    def __init__(
        self,
        clock: Clock,
        scheduler: Scheduler,
        *,
        max_extensions: int = DEFAULT_MAX_EXTENSIONS,
        extension_seconds: int = DEFAULT_EXTENSION_SECONDS,
        idea_walk_seconds: int = DEFAULT_IDEA_WALK_SECONDS,
        on_recovery_due: Callable[[], None] | None = None,
        on_idea_walk_ended: Callable[[], None] | None = None,
    ) -> None:
        self._clock = clock
        self._max_extensions = max_extensions
        self._extension_seconds = extension_seconds
        self._idea_walk_seconds = idea_walk_seconds
        self._on_recovery_due = on_recovery_due or (lambda: None)
        self._on_idea_walk_ended = on_idea_walk_ended or (lambda: None)

        self._state = FocusState.STOPPED
        self._presence = PresenceState.ACTIVE
        self._plan: FocusPlan | None = None
        self._started_at_utc: datetime | None = None
        self._active_seconds = 0.0
        self._extension_seconds_used = 0
        self._extensions_used = 0
        self._used_finish_thought = False
        self._accruing = False
        self._checkpoint_ns = 0
        self._away_started_ns = clock.monotonic_ns()

        self._focus_budget = DeadlineBudget(clock, scheduler, _FOCUS_KEY, self._handle_focus_due)
        self._idea_walk_budget = DeadlineBudget(
            clock, scheduler, _IDEA_WALK_KEY, self._handle_idea_walk_due
        )

    # -- read-only state -------------------------------------------------

    @property
    def state(self) -> FocusState:
        return self._state

    @property
    def presence(self) -> PresenceState:
        return self._presence

    @property
    def active_seconds(self) -> float:
        """Elapsed focus time, excluding any non-``ACTIVE`` presence
        periods and any time spent paused."""
        if self._accruing:
            return self._active_seconds + self._elapsed_since_checkpoint()
        return self._active_seconds

    @property
    def remaining_seconds(self) -> float:
        return self._focus_budget.remaining_seconds

    @property
    def extensions_used(self) -> int:
        return self._extensions_used

    @property
    def max_extensions(self) -> int:
        return self._max_extensions

    @property
    def plan(self) -> FocusPlan | None:
        """The plan the current (or most recently active) session was
        started with, or ``None`` before any session has started. Read-only
        — exists so a caller (Phase 4's crash-recovery checkpointing) can
        snapshot enough to reconstruct the session without reaching into
        engine internals."""
        return self._plan

    @property
    def started_at_utc(self) -> datetime | None:
        return self._started_at_utc

    # -- lifecycle --------------------------------------------------------

    def start(self, plan: FocusPlan) -> None:
        if self._state not in (FocusState.STOPPED, FocusState.READY):
            raise InvalidStateTransition(f"cannot start a session from {self._state}")
        self._plan = plan
        self._started_at_utc = self._clock.utc_now()
        self._active_seconds = 0.0
        self._extension_seconds_used = 0
        self._extensions_used = 0
        self._used_finish_thought = False
        self._away_started_ns = self._clock.monotonic_ns()
        self._state = FocusState.FOCUSING
        self._enter_focusing(plan.durations.focus_seconds)

    def pause(self) -> None:
        if self._state is not FocusState.FOCUSING:
            raise InvalidStateTransition(f"cannot pause from {self._state}")
        self._freeze_active_time()
        self._focus_budget.freeze()
        self._state = FocusState.PAUSED

    def resume(self) -> None:
        if self._state is not FocusState.PAUSED:
            raise InvalidStateTransition(f"cannot resume from {self._state}")
        self._state = FocusState.FOCUSING
        self._enter_focusing(self._focus_budget.remaining_seconds)

    def extend(self, seconds: int | None = None) -> int:
        """Extend a session that's due for recovery. Returns the total
        number of extensions used so far this session."""
        if self._state is not FocusState.RECOVERY_DUE:
            raise InvalidStateTransition(f"cannot extend from {self._state}")
        if self._extensions_used >= self._max_extensions:
            raise InvalidStateTransition(
                f"maximum of {self._max_extensions} extensions already used for this session"
            )
        amount = seconds if seconds is not None else self._extension_seconds
        self._extensions_used += 1
        self._extension_seconds_used += amount
        self._state = FocusState.FOCUSING
        self._enter_focusing(amount)
        return self._extensions_used

    def finish_current_thought(self, seconds: int = DEFAULT_FINISH_THOUGHT_SECONDS) -> None:
        """A single short grace period, distinct from a real extension —
        ``ScreenCare — Concept.md`` lists it as its own Flow Protection
        option alongside Start Break and Extend 5 Minutes, and it doesn't
        count against the extension limit."""
        if self._state is not FocusState.RECOVERY_DUE:
            raise InvalidStateTransition(f"cannot finish current thought from {self._state}")
        if self._used_finish_thought:
            raise InvalidStateTransition("finish_current_thought already used for this session")
        self._used_finish_thought = True
        self._state = FocusState.FOCUSING
        self._enter_focusing(seconds)

    def start_break(self) -> None:
        if self._state is not FocusState.RECOVERY_DUE:
            raise InvalidStateTransition(f"cannot start a break from {self._state}")
        self._state = FocusState.BREAKING

    def end_break(self) -> FocusSessionSummary:
        if self._state is not FocusState.BREAKING:
            raise InvalidStateTransition(f"cannot end a break from {self._state}")
        summary = self._finish(FocusOutcome.COMPLETED)
        self._state = FocusState.READY
        return summary

    def start_idea_walk(self) -> None:
        if self._state is not FocusState.FOCUSING:
            raise InvalidStateTransition(f"cannot start an idea walk from {self._state}")
        self._freeze_active_time()
        self._focus_budget.freeze()
        self._state = FocusState.IDEA_WALK
        self._idea_walk_budget.arm(self._idea_walk_seconds)

    def return_from_idea_walk(self, *, resume_focus: bool = True) -> FocusSessionSummary | None:
        if self._state is not FocusState.IDEA_WALK:
            raise InvalidStateTransition(f"cannot return from an idea walk from {self._state}")
        self._idea_walk_budget.cancel()
        if resume_focus:
            self._state = FocusState.FOCUSING
            self._enter_focusing(self._focus_budget.remaining_seconds)
            return None
        summary = self._finish(FocusOutcome.INTERRUPTED)
        self._state = FocusState.READY
        return summary

    def stop(self, *, outcome: FocusOutcome = FocusOutcome.ABANDONED) -> FocusSessionSummary | None:
        """Give up on the session from any in-progress state. A no-op
        (returns ``None``) if there's nothing active to stop."""
        if self._state in (FocusState.STOPPED, FocusState.READY):
            self._state = FocusState.STOPPED
            return None
        summary = self._finish(outcome)
        self._state = FocusState.STOPPED
        return summary

    def acknowledge_ready(self) -> None:
        """Move on from ``READY`` once the break screen has been
        dismissed."""
        if self._state is not FocusState.READY:
            raise InvalidStateTransition(f"cannot acknowledge from {self._state}")
        self._state = FocusState.STOPPED

    # -- presence -----------------------------------------------------------

    def on_presence_changed(self, new_presence: PresenceState) -> float | None:
        """Tell the engine presence changed.

        Returns the away-duration in seconds if this call was a return to
        ``ACTIVE`` from a non-active state during a focus or idea-walk
        period (useful for break-crediting via
        :meth:`~screencare.engines.break_engine.BreakEngine.qualifies_as_break`),
        otherwise ``None``.
        """
        was_active = self._presence is PresenceState.ACTIVE
        now_active = new_presence is PresenceState.ACTIVE
        away_seconds: float | None = None

        # Update presence before touching any budget: _enter_focusing()
        # (and _idea_walk_budget.arm()) below decide whether to actually
        # re-arm based on self._presence, so it must already reflect the
        # new value by the time they run.
        self._presence = new_presence

        if was_active and not now_active:
            if self._state is FocusState.FOCUSING:
                self._freeze_active_time()
                self._focus_budget.freeze()
                self._away_started_ns = self._clock.monotonic_ns()
            elif self._state is FocusState.IDEA_WALK:
                self._idea_walk_budget.freeze()
                self._away_started_ns = self._clock.monotonic_ns()
        elif not was_active and now_active:
            if self._state is FocusState.FOCUSING:
                away_seconds = self._away_seconds_elapsed()
                self._enter_focusing(self._focus_budget.remaining_seconds)
            elif self._state is FocusState.IDEA_WALK:
                away_seconds = self._away_seconds_elapsed()
                remaining = self._idea_walk_budget.remaining_seconds
                if remaining > 0:
                    self._idea_walk_budget.arm(remaining)

        return away_seconds

    # -- internals --------------------------------------------------------

    def _enter_focusing(self, remaining_seconds: float) -> None:
        """(Re)start accruing active time and, if presence allows it, arm
        the focus deadline for ``remaining_seconds``. Shared by every path
        that lands in ``FOCUSING`` with a known remaining budget: a fresh
        start, resuming from pause, an extension, finishing a thought,
        returning from an idea walk, or presence coming back to active."""
        self._checkpoint_ns = self._clock.monotonic_ns()
        self._accruing = self._presence is PresenceState.ACTIVE
        if self._accruing and remaining_seconds > 0:
            self._focus_budget.arm(remaining_seconds)
        elif not self._accruing:
            self._away_started_ns = self._clock.monotonic_ns()

    def _freeze_active_time(self) -> None:
        if self._accruing:
            self._active_seconds += self._elapsed_since_checkpoint()
        self._accruing = False

    def _elapsed_since_checkpoint(self) -> float:
        return (self._clock.monotonic_ns() - self._checkpoint_ns) / 1_000_000_000

    def _away_seconds_elapsed(self) -> float:
        return (self._clock.monotonic_ns() - self._away_started_ns) / 1_000_000_000

    def _handle_focus_due(self) -> None:
        self._freeze_active_time()
        self._state = FocusState.RECOVERY_DUE
        self._on_recovery_due()

    def _handle_idea_walk_due(self) -> None:
        """The idea walk timed out without an explicit return — resume
        focusing automatically rather than leaving the session stranded
        (``ScreenCare — Technical.md`` section 15: "Do not require the
        user to keep the Idea Walk screen open.")."""
        self._state = FocusState.FOCUSING
        self._enter_focusing(self._focus_budget.remaining_seconds)
        self._on_idea_walk_ended()

    def _finish(self, outcome: FocusOutcome) -> FocusSessionSummary:
        if self._plan is None or self._started_at_utc is None:
            raise InvalidStateTransition("no active session to finish")
        self._freeze_active_time()
        self._focus_budget.cancel()
        self._idea_walk_budget.cancel()
        return FocusSessionSummary(
            mode=self._plan.mode,
            task_label=self._plan.task_label,
            started_at_utc=self._started_at_utc,
            ended_at_utc=self._clock.utc_now(),
            planned_seconds=self._plan.durations.focus_seconds,
            active_seconds=int(self._active_seconds),
            extension_seconds=self._extension_seconds_used,
            outcome=outcome,
        )
