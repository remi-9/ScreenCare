"""``AppSession``: the application layer that wires the Phase 2 engines, the
``WellnessCoordinator``, persistence, and notifications together — the
"PySide6 Application Layer" / "WellnessCoordinator" boxes in
``ARCHITECTURE.md``'s target shape.

Deliberately Qt-free. It's driven by whatever calls its methods and
:meth:`AppSession.tick`: in the real app that's ``app/bootstrap.py`` (a
``QTimer`` for ``tick()``, view-model slots for everything else); in tests
it's a plain loop over a :class:`~screencare.scheduler.clock.FakeClock`. That
split is what makes the whole session-lifecycle/notification-merging/
crash-recovery-checkpointing logic fully unit-testable without PySide6
installed — the same reason ``screencare.engines`` has no Qt dependency.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from screencare.activity.base import ActivityProvider, PowerMonitor
from screencare.activity.presence_monitor import DEFAULT_IDLE_THRESHOLD_SECONDS, PresenceMonitor
from screencare.domain.enums import (
    BreakCompletionSource,
    BreakKind,
    FocusFeedback,
    FocusMode,
    FocusState,
    NotificationPriority,
    PresenceState,
)
from screencare.domain.models import (
    ADAPTIVE_DEFAULT_RECOVERY_SECONDS,
    CLASSIC_DURATIONS,
    DEEP_FOCUS_DURATIONS,
    BreakSession,
    FocusDurations,
    FocusPlan,
    FocusSessionSummary,
)
from screencare.engines.adaptive_focus import AdaptiveFocusEngine
from screencare.engines.break_engine import BreakEngine
from screencare.engines.eye_rest_engine import EyeRestEngine, EyeRestSettings
from screencare.engines.focus_engine import FocusEngine
from screencare.engines.hydration_engine import HydrationEngine, HydrationSettings
from screencare.engines.wellness_coordinator import RecoveryDecision, WellnessCoordinator
from screencare.notifications.base import Notification, NotificationService
from screencare.persistence.repositories import (
    BreakSessionRepository,
    FocusSessionRepository,
    HydrationEventRepository,
    IdeaWalkNoteRepository,
)
from screencare.persistence.session_recovery import (
    RecoveryAction,
    SessionSnapshot,
    SessionSnapshotRepository,
    reconcile_startup_snapshot,
)
from screencare.persistence.settings import AppSettings
from screencare.scheduler.clock import Clock
from screencare.scheduler.scheduler import Scheduler

# "Database session writes <= 1/minute except transitions" — Technical.md §27.
CHECKPOINT_MIN_INTERVAL_SECONDS = 60.0
_IN_PROGRESS_STATES = (FocusState.FOCUSING, FocusState.PAUSED, FocusState.IDEA_WALK)

_RECOVERY_NOTIFICATION_ID = "recovery_due"
_HYDRATION_NOTIFICATION_ID = "hydration_due"


@dataclass(frozen=True)
class StartupRecovery:
    """What :meth:`AppSession.reconcile_startup` found — for the UI to
    optionally show a "the app closed unexpectedly" notice. Never claims a
    session *completed*; see ``session_recovery.reconcile_startup_snapshot``.
    """

    action: RecoveryAction
    snapshot: SessionSnapshot | None


class AppSession:
    def __init__(
        self,
        *,
        clock: Clock,
        scheduler: Scheduler,
        settings: AppSettings,
        focus_repo: FocusSessionRepository,
        break_repo: BreakSessionRepository,
        hydration_repo: HydrationEventRepository,
        idea_walk_note_repo: IdeaWalkNoteRepository,
        snapshot_repo: SessionSnapshotRepository,
        notifier: NotificationService,
        activity_provider: ActivityProvider | None = None,
        power_monitor: PowerMonitor | None = None,
        idle_threshold_seconds: float = DEFAULT_IDLE_THRESHOLD_SECONDS,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        self._clock = clock
        self._scheduler = scheduler
        self._settings = settings
        self._focus_repo = focus_repo
        self._break_repo = break_repo
        self._hydration_repo = hydration_repo
        self._idea_walk_note_repo = idea_walk_note_repo
        self._snapshot_repo = snapshot_repo
        self._notifier = notifier
        self._power_monitor = power_monitor
        self._presence_monitor = PresenceMonitor(
            provider=activity_provider, idle_threshold_seconds=idle_threshold_seconds
        )
        self._presence = PresenceState.ACTIVE
        self._power_monitor_started = False
        self._on_changed = on_changed or (lambda: None)

        self._adaptive = AdaptiveFocusEngine(initial_seconds=settings.focus_minutes * 60)
        self._coordinator = WellnessCoordinator(hydration_settings=self._hydration_settings())

        self._focus = FocusEngine(
            clock,
            scheduler,
            on_recovery_due=self._handle_recovery_due,
            on_idea_walk_ended=self._handle_idea_walk_ended,
        )
        self._break_engine = BreakEngine(clock)
        self._hydration = HydrationEngine(
            clock, scheduler, settings=self._hydration_settings(), on_due=self._handle_hydration_due
        )
        self._eye_rest = EyeRestEngine(
            clock,
            scheduler,
            settings=EyeRestSettings(
                interval_seconds=settings.eye_reminder_minutes * 60,
                enabled=settings.eye_reminder_enabled,
            ),
            on_due=self._handle_eye_rest_due,
        )

        self._current_break: BreakSession | None = None
        self._recovery_included_hydration = False
        self._reminder_text = ""
        self._last_checkpoint_ns = clock.monotonic_ns()
        self._checkpoint_dirty = False
        self._started = False
        self._quiet_until_utc: datetime | None = None

    def _hydration_settings(self) -> HydrationSettings:
        return HydrationSettings(
            interval_seconds=self._settings.hydration_interval_minutes * 60,
            strict=self._settings.hydration_strict,
        )

    # -- startup / shutdown --------------------------------------------------

    def reconcile_startup(self) -> StartupRecovery:
        """Must be called once, before :meth:`begin`. Reads whatever crash
        snapshot exists and always clears it — a resumed or interrupted
        session either way starts fresh from here, never a half-restored
        in-progress state (Technical.md §23: never invent completed work)."""
        snapshot = self._snapshot_repo.load()
        outcome = reconcile_startup_snapshot(snapshot, self._clock.utc_now())
        if outcome.action is not RecoveryAction.NONE:
            self._snapshot_repo.clear()
        return StartupRecovery(action=outcome.action, snapshot=outcome.snapshot)

    def begin(self) -> None:
        """Start the always-on background reminders. Call once, after
        :meth:`reconcile_startup`. Hydration runs continuously regardless of
        focus state (Concept.md's hourly reminder isn't tied to a session);
        eye-rest only runs while actually focusing, so it starts/stops with
        each session instead."""
        if not self._started:
            self._hydration.start()
            self._started = True
        self._maybe_start_power_monitor()

    def attach_platform_adapters(
        self,
        *,
        activity_provider: ActivityProvider | None = None,
        power_monitor: PowerMonitor | None = None,
    ) -> None:
        """Attach platform adapters discovered *after* construction. The
        real app can only build the Windows session monitor once the QML
        root window exists (it needs a native window handle to register
        for session notifications), which is after ``AppSession`` itself
        is built and :meth:`begin` has already run -- so this is the hook
        ``bootstrap.py`` calls once that window is available. Safe to call
        with either argument, or both, at most once each."""
        if activity_provider is not None:
            self._presence_monitor.set_provider(activity_provider)
        if power_monitor is not None:
            self._power_monitor = power_monitor
            self._maybe_start_power_monitor()

    def _maybe_start_power_monitor(self) -> None:
        if self._power_monitor is not None and not self._power_monitor_started:
            self._power_monitor.start(
                on_sleep=self.on_platform_sleep, on_wake=self.on_platform_wake
            )
            self._power_monitor_started = True

    def shutdown(self) -> None:
        """Persist a final checkpoint before the process exits
        (Technical.md §18: "Explicit Quit: persist state ... exit process").
        """
        if self._power_monitor is not None:
            self._power_monitor.stop()
        self._checkpoint(force=True)

    # -- read-only state exposed to view models ------------------------------

    @property
    def focus_state(self) -> FocusState:
        return self._focus.state

    @property
    def focus_mode(self) -> FocusMode | None:
        plan = self._focus.plan
        return plan.mode if plan else None

    @property
    def task_label(self) -> str | None:
        plan = self._focus.plan
        return plan.task_label if plan else None

    @property
    def remaining_seconds(self) -> float:
        return self._focus.remaining_seconds

    @property
    def active_seconds(self) -> float:
        return self._focus.active_seconds

    @property
    def extensions_used(self) -> int:
        return self._focus.extensions_used

    @property
    def max_extensions(self) -> int:
        return self._focus.max_extensions

    @property
    def pending_recovery_includes_hydration(self) -> bool:
        return self._recovery_included_hydration

    @property
    def reminder_text(self) -> str:
        """A gentle, in-app-only visual (never an OS notification) for a due
        eye-rest prompt or a hydration reminder that fired standalone.
        Empty string when there's nothing to show."""
        return self._reminder_text

    @property
    def hydration_seconds_until_due(self) -> float:
        return self._hydration.seconds_until_due

    @property
    def adaptive_focus_seconds(self) -> int:
        return self._adaptive.current_duration_seconds

    @property
    def presence(self) -> PresenceState:
        return self._presence

    @property
    def is_quiet(self) -> bool:
        return self._quiet_until_utc is not None and self._clock.utc_now() < self._quiet_until_utc

    @property
    def quiet_seconds_remaining(self) -> float:
        if self._quiet_until_utc is None:
            return 0.0
        return max(0.0, (self._quiet_until_utc - self._clock.utc_now()).total_seconds())

    # -- quiet mode -----------------------------------------------------------

    def enter_quiet_mode(self, minutes: int | None = None) -> None:
        """``ScreenCare — Technical.md`` section 17: "provide 'Pause
        reminders for 30/60/120 minutes'". Only suppresses the *delivery* of
        hydration/recovery notifications (tray balloon and the in-app
        banner) -- the underlying engines keep running exactly as before,
        so nothing is lost, just not announced, and the recovery break
        screen still works normally the next time the app is opened."""
        duration = minutes if minutes is not None else self._settings.quiet_mode_minutes
        self._quiet_until_utc = self._clock.utc_now() + timedelta(minutes=duration)
        self._changed()

    def exit_quiet_mode(self) -> None:
        self._quiet_until_utc = None
        self._changed()

    # -- presence (Phase 5: idle / lock / sleep-wake) --------------------------

    def on_platform_sleep(self) -> None:
        """Called by the platform power monitor right before the system
        suspends. Persist first (``ScreenCare — Technical.md`` section 12:
        "1. Persist current state."), then mark presence -- so a crash
        during suspend still leaves a recoverable snapshot, and no ticks
        that occur while suspended (there generally aren't any) could ever
        be mistaken for focus time."""
        self._checkpoint(force=True)
        self._presence_monitor.mark_sleeping()
        self._apply_presence(PresenceState.SLEEPING)

    def on_platform_wake(self) -> None:
        """Called right after the system resumes. Queries the *real*
        idle/lock state rather than assuming ``ACTIVE`` (Technical.md
        section 12: "3. Query actual idle state.")."""
        self._presence_monitor.mark_awake()
        self._apply_presence(self._presence_monitor.poll())

    def _apply_presence(self, new_presence: PresenceState) -> None:
        """The single place presence transitions are applied, whether
        discovered by polling (:meth:`tick`) or pushed by a platform event
        (sleep/wake above). Freezing/resuming hydration and eye-rest mirror
        what :meth:`start_idea_walk` already does explicitly, but are
        skipped during an idea walk (which owns that freeze/thaw itself)
        and eye-rest is skipped unless actually focusing (pausing already
        freezes it independently, and presence must not un-freeze a
        deliberately paused session)."""
        if new_presence == self._presence:
            return
        was_active = self._presence is PresenceState.ACTIVE
        now_active = new_presence is PresenceState.ACTIVE
        in_idea_walk = self._focus.state is FocusState.IDEA_WALK
        is_focusing = self._focus.state is FocusState.FOCUSING

        if was_active and not now_active:
            if not in_idea_walk:
                self._hydration.freeze()
            if is_focusing:
                self._eye_rest.freeze()

        away_seconds = self._focus.on_presence_changed(new_presence)
        self._presence = new_presence

        if not was_active and now_active:
            if not in_idea_walk:
                self._hydration.resume()
            if is_focusing:
                self._eye_rest.resume()
            if away_seconds and self._break_engine.qualifies_as_break(away_seconds):
                self._record_away_break(away_seconds)

        self._checkpoint(force=True)
        self._changed()

    def _record_away_break(self, away_seconds: float) -> None:
        """An idle/locked/sleeping period long enough to qualify as a real
        computer break, credited automatically -- never claimed as a "walk
        completed" (``ScreenCare — Technical.md`` section 14), just an
        away-from-computer break."""
        ended_at = self._clock.utc_now()
        away_int = int(away_seconds)
        self._break_repo.insert(
            BreakSession(
                kind=BreakKind.AWAY,
                started_at_utc=ended_at - timedelta(seconds=away_int),
                ended_at_utc=ended_at,
                away_seconds=away_int,
                completion_source=BreakCompletionSource.IDLE_DETECTED,
            )
        )

    # -- focus lifecycle ------------------------------------------------------

    def start_focus(self, mode: FocusMode, task_label: str | None = None) -> None:
        plan = FocusPlan(mode=mode, durations=self._durations_for(mode), task_label=task_label)
        self._focus.start(plan)
        self._eye_rest.start()
        self._mark_dirty()

    def pause(self) -> None:
        self._focus.pause()
        self._eye_rest.freeze()
        self._mark_dirty()

    def resume(self) -> None:
        self._focus.resume()
        self._eye_rest.resume()
        self._mark_dirty()

    def extend(self, seconds: int | None = None) -> int:
        result = self._focus.extend(seconds)
        self._mark_dirty()
        return result

    def finish_current_thought(self) -> None:
        self._focus.finish_current_thought()
        self._mark_dirty()

    def start_break(self) -> None:
        self._current_break = self._break_engine.start(BreakKind.RECOVERY)
        self._focus.start_break()
        self._mark_dirty()

    def end_break(self, *, feedback: FocusFeedback | None = None) -> FocusSessionSummary:
        if self._current_break is not None:
            ended = self._break_engine.end(
                self._current_break, completion_source=BreakCompletionSource.USER_CONFIRMED
            )
            self._break_repo.insert(ended)
            self._current_break = None
        if self._recovery_included_hydration:
            # The break suggested hydration; assume the user acted on the
            # suggestion and restart the interval rather than immediately
            # re-firing (Concept.md: "hydration should be mergeable into a
            # nearby focus/recovery break").
            self._hydration.start()
            self._recovery_included_hydration = False

        summary = self._focus.end_break()
        if feedback is not None:
            summary = replace(summary, feedback=feedback)
            self._adaptive.record_outcome(
                feedback=feedback, completion_rate=summary.completion_rate
            )
        self._focus_repo.insert(summary)
        self._snapshot_repo.clear()
        self._notifier.withdraw(_RECOVERY_NOTIFICATION_ID)
        self._mark_dirty()
        return summary

    def start_idea_walk(self) -> None:
        self._focus.start_idea_walk()
        # "No eye/hydration/movement notifications should fire" during an
        # idea walk -- Technical.md §15. Both are independent of the focus
        # session otherwise, so they're frozen here specifically rather than
        # as part of the general pause/stop paths.
        self._eye_rest.freeze()
        self._hydration.freeze()
        self._mark_dirty()

    def _handle_idea_walk_ended(self) -> None:
        """The idea walk timed out on its own and ``FocusEngine`` already
        resumed ``FOCUSING`` internally before invoking this callback
        (``ScreenCare — Technical.md`` section 15: "Do not require the user
        to keep the Idea Walk screen open."). This is the *only* path back
        from an idea walk that doesn't go through
        :meth:`return_from_idea_walk`, so it must thaw the same things
        :meth:`start_idea_walk` froze."""
        self._eye_rest.resume()
        self._hydration.resume()
        self._changed()

    def return_from_idea_walk(
        self, *, resume_focus: bool = True, note: str | None = None
    ) -> FocusSessionSummary | None:
        if note:
            self._idea_walk_note_repo.insert(note)
        summary = self._focus.return_from_idea_walk(resume_focus=resume_focus)
        self._hydration.resume()
        if resume_focus:
            self._eye_rest.resume()
        else:
            self._eye_rest.stop()
            if summary is not None:
                self._focus_repo.insert(summary)
            self._snapshot_repo.clear()
        self._mark_dirty()
        return summary

    def acknowledge_ready(self) -> None:
        self._focus.acknowledge_ready()
        self._changed()

    def stop(self) -> FocusSessionSummary | None:
        summary = self._focus.stop()
        self._eye_rest.stop()
        self._current_break = None
        self._recovery_included_hydration = False
        if summary is not None:
            self._focus_repo.insert(summary)
        self._snapshot_repo.clear()
        self._notifier.withdraw(_RECOVERY_NOTIFICATION_ID)
        self._changed()
        return summary

    # -- wellness actions -----------------------------------------------------

    def log_drink(self) -> None:
        event = self._hydration.log_drink()
        self._hydration_repo.insert(event)
        if self._reminder_text:
            self._reminder_text = ""
        self._notifier.withdraw(_HYDRATION_NOTIFICATION_ID)
        self._changed()

    def dismiss_reminder(self) -> None:
        """The user saw the in-app eye-rest/hydration banner; clear it and
        (for eye-rest) start counting toward the next one."""
        self._reminder_text = ""
        if self._eye_rest.is_due:
            self._eye_rest.acknowledge()
        self._changed()

    def apply_settings_changed(self) -> None:
        """Call after a setting affecting an armed countdown (hydration
        interval/strict, eye-rest interval/enabled) changes, so the new
        value takes effect on its *next* countdown rather than retroactively
        rewriting one already in flight."""
        self._coordinator = WellnessCoordinator(hydration_settings=self._hydration_settings())
        self._hydration.settings = self._hydration_settings()
        self._eye_rest.settings = EyeRestSettings(
            interval_seconds=self._settings.eye_reminder_minutes * 60,
            enabled=self._settings.eye_reminder_enabled,
        )

    # -- driving the scheduler --------------------------------------------------

    def tick(self) -> None:
        # Polling every tick (rather than only reacting to platform events)
        # is also the fallback for a missed sleep/wake or lock/unlock event
        # (Technical.md §41: "the scheduler must still notice a large
        # discrepancy ... and trigger reconciliation") -- the next real
        # tick after any gap re-queries actual idle/lock state.
        self._apply_presence(self._presence_monitor.poll())
        fired = self._scheduler.tick()
        if fired:
            self._checkpoint_dirty = True
        self._checkpoint(force=False)
        if fired:
            self._changed()

    # -- internals: durations -------------------------------------------------

    def _durations_for(self, mode: FocusMode) -> FocusDurations:
        if mode is FocusMode.CLASSIC:
            return CLASSIC_DURATIONS
        if mode is FocusMode.DEEP_FOCUS:
            return DEEP_FOCUS_DURATIONS
        return FocusDurations(
            focus_seconds=self._adaptive.current_duration_seconds,
            recovery_seconds=ADAPTIVE_DEFAULT_RECOVERY_SECONDS,
        )

    # -- internals: notification decisions -------------------------------------

    def _handle_recovery_due(self) -> None:
        decision: RecoveryDecision = self._coordinator.decide_recovery(
            recovery_due_in_seconds=0,
            hydration_due_in_seconds=(
                self._hydration.seconds_until_due if self._hydration_engine_running() else None
            ),
            eye_rest_overdue=self._eye_rest.is_due,
        )
        self._eye_rest.stop()
        self._recovery_included_hydration = decision.include_hydration
        self._reminder_text = ""  # the recovery break screen replaces any standalone banner

        lines = ["Time for a reset."]
        if decision.include_hydration and decision.include_eye_rest:
            lines.append("Walk around, rest your eyes, and get some water.")
        elif decision.include_hydration:
            lines.append("Walk around and get some water.")
        elif decision.include_eye_rest:
            lines.append("Walk around and rest your eyes.")
        else:
            lines.append("Walk around for a few minutes.")

        if not self.is_quiet:
            self._notifier.send(
                Notification(
                    id=_RECOVERY_NOTIFICATION_ID,
                    title="Focus complete",
                    message=" ".join(lines),
                    priority=NotificationPriority.P3_RECOVERY_DUE,
                )
            )
        self._checkpoint(force=True)
        self._changed()

    def _handle_hydration_due(self) -> None:
        is_focusing = self._focus.state is FocusState.FOCUSING
        recovery_due_in = self.remaining_seconds if is_focusing else None
        should_fire = self._coordinator.should_fire_hydration_standalone(
            hydration_due_in_seconds=0,
            recovery_due_in_seconds=recovery_due_in,
        )
        if should_fire and not self.is_quiet:
            self._reminder_text = "Time to drink some water."
            self._notifier.send(
                Notification(
                    id=_HYDRATION_NOTIFICATION_ID,
                    title="Hydration",
                    message=self._reminder_text,
                    priority=NotificationPriority.P1_GENTLE,
                )
            )
        self._changed()

    def _handle_eye_rest_due(self) -> None:
        # Deliberately no OS notification here — Implementation Standards.md
        # §22: eye-rest prompts must be subtle and must not aggressively
        # interrupt a focus session. A quiet in-app banner is enough.
        if not self.is_quiet:
            self._reminder_text = "Rest your eyes — look into the distance for a moment."
        self._changed()

    def _hydration_engine_running(self) -> bool:
        return self._started

    # -- internals: crash-recovery checkpointing -------------------------------

    def _mark_dirty(self) -> None:
        self._checkpoint_dirty = True
        self._checkpoint(force=True)
        self._changed()

    def _checkpoint(self, *, force: bool) -> None:
        if self._focus.state not in _IN_PROGRESS_STATES:
            return
        if not force:
            elapsed = (self._clock.monotonic_ns() - self._last_checkpoint_ns) / 1_000_000_000
            if not self._checkpoint_dirty and elapsed < CHECKPOINT_MIN_INTERVAL_SECONDS:
                return
        plan = self._focus.plan
        started_at = self._focus.started_at_utc
        if plan is None or started_at is None:
            return
        self._snapshot_repo.save(
            SessionSnapshot(
                mode=plan.mode,
                task_label=plan.task_label,
                started_at_utc=started_at,
                planned_seconds=plan.durations.focus_seconds,
                active_seconds=int(self._focus.active_seconds),
                last_checkpoint_utc=self._clock.utc_now(),
            )
        )
        self._last_checkpoint_ns = self._clock.monotonic_ns()
        self._checkpoint_dirty = False

    def _changed(self) -> None:
        self._on_changed()
