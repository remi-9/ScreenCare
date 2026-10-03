"""All of ScreenCare's product rules, as one pure function.

    apply(session, settings, action, payload, now) -> (session, events)

The browser keeps the session in localStorage and sends it with every action;
nothing here does I/O or reads the clock. Every countdown is a ``Timer`` that
is either *running* (has ``due_at``) or *frozen* (has ``left_s``), so a page
reload, a sleeping laptop, or a closed tab never loses or double-counts time.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, Field


def _clamped(lo: int, hi: int):
    return AfterValidator(lambda v: max(lo, min(hi, v)))


class Mode(StrEnum):
    CLASSIC = "classic"
    DEEP = "deep"
    ADAPTIVE = "adaptive"


class Phase(StrEnum):
    IDLE = "idle"
    FOCUSING = "focusing"
    PAUSED = "paused"
    RECOVERY_DUE = "recovery_due"
    BREAKING = "breaking"
    IDEA_WALK = "idea_walk"


class Feedback(StrEnum):
    TOO_SHORT = "too_short"
    JUST_RIGHT = "just_right"
    TOO_LONG = "too_long"


# (focus, recovery) seconds. Adaptive focus comes from the session instead.
DURATIONS = {Mode.CLASSIC: (25 * 60, 5 * 60), Mode.DEEP: (50 * 60, 8 * 60)}
ADAPTIVE_RECOVERY_S = 7 * 60
ADAPTIVE_MIN_S, ADAPTIVE_MAX_S, ADAPTIVE_STEP_S = 20 * 60, 60 * 60, 5 * 60

MAX_EXTENSIONS = 2
EXTENSION_S = 5 * 60
FINISH_THOUGHT_S = 2 * 60
IDEA_WALK_S = 5 * 60
AWAY_COUNTS_AS_BREAK_S = 3 * 60
HYDRATION_MERGE_WINDOW_S = 10 * 60


class Settings(BaseModel):
    hydration_minutes: Annotated[int, _clamped(30, 180)] = 60
    hydration_strict: bool = False
    eye_rest_enabled: bool = True
    eye_rest_minutes: Annotated[int, _clamped(10, 60)] = 20
    quiet_minutes: Annotated[int, _clamped(15, 240)] = 60


class Timer(BaseModel):
    due_at: datetime | None = None
    left_s: float | None = None

    @property
    def running(self) -> bool:
        return self.due_at is not None

    def start(self, seconds: float, now: datetime) -> None:
        self.due_at, self.left_s = now + timedelta(seconds=seconds), None

    def freeze(self, at: datetime) -> None:
        if self.due_at is not None:
            self.left_s = max(0.0, (self.due_at - at).total_seconds())
            self.due_at = None

    def thaw(self, now: datetime) -> None:
        if self.left_s is not None:
            self.start(self.left_s, now)

    def clear(self) -> None:
        self.due_at = self.left_s = None

    def remaining(self, now: datetime) -> float | None:
        if self.due_at is not None:
            return max(0.0, (self.due_at - now).total_seconds())
        return self.left_s


class Session(BaseModel):
    phase: Phase = Phase.IDLE
    mode: Mode | None = None
    task: Annotated[str, Field(max_length=200)] | None = None
    started_at: datetime | None = None
    planned_s: int = 0
    recovery_s: int = 0
    active_s: float = 0.0
    active_since: datetime | None = None
    extensions_used: int = 0
    extension_s: int = 0
    finish_thought_used: bool = False
    break_started_at: datetime | None = None
    hydration_pending: bool = False
    eye_pending: bool = False
    away_since: datetime | None = None
    quiet_until: datetime | None = None
    adaptive_focus_s: Annotated[int, _clamped(ADAPTIVE_MIN_S, ADAPTIVE_MAX_S)] = 25 * 60

    focus: Timer = Field(default_factory=Timer)
    rest: Timer = Field(default_factory=Timer)  # break or idea-walk countdown
    hydration: Timer = Field(default_factory=Timer)
    eye: Timer = Field(default_factory=Timer)


class InvalidAction(ValueError):
    """The action isn't valid from the session's current phase."""


Event = dict[str, Any]


def apply(
    session: Session,
    settings: Settings,
    action: str,
    payload: dict[str, Any] | None,
    now: datetime,
) -> tuple[Session, list[Event]]:
    handler = _ACTIONS.get(action)
    if handler is None:
        raise InvalidAction(f"unknown action {action!r}")
    s = session.model_copy(deep=True)
    ctx = _Ctx(s, settings, now, payload or {})
    if not s.hydration.running and s.hydration.left_s is None:
        s.hydration.start(settings.hydration_minutes * 60, now)
    # Presence changes are applied *before* firing due timers: a report that
    # the user left at `since` must freeze timers as of then, not let them
    # fire for time the user wasn't there.
    if action in ("away", "back"):
        handler(ctx)
        _fire_due(ctx)
    else:
        _fire_due(ctx)
        handler(ctx)
    return s, ctx.events


class _Ctx:
    def __init__(self, s: Session, settings: Settings, now: datetime, payload: dict) -> None:
        self.s, self.settings, self.now, self.payload = s, settings, now, payload
        self.events: list[Event] = []

    @property
    def quiet(self) -> bool:
        return self.s.quiet_until is not None and self.now < self.s.quiet_until

    def notify(self, title: str, body: str, kind: str) -> None:
        if not self.quiet:
            self.events.append({"event": "notify", "title": title, "body": body, "type": kind})

    def banner(self, text: str, kind: str) -> None:
        if not self.quiet:
            self.events.append({"event": "banner", "text": text, "type": kind})

    def record(self, **fields: Any) -> None:
        self.events.append({"event": "record", **fields})

    def require(self, *phases: Phase) -> None:
        if self.s.phase not in phases:
            raise InvalidAction(f"can't do that while {self.s.phase.value.replace('_', ' ')}")


# -- active-time accrual -------------------------------------------------------


def _accrue_start(s: Session, at: datetime) -> None:
    if s.away_since is None:
        s.active_since = at


def _accrue_stop(s: Session, at: datetime) -> None:
    if s.active_since is not None:
        s.active_s += max(0.0, (at - s.active_since).total_seconds())
        s.active_since = None


def _enter_focusing(ctx: _Ctx, seconds: float) -> None:
    s = ctx.s
    s.phase = Phase.FOCUSING
    s.focus.start(seconds, ctx.now)
    _accrue_start(s, ctx.now)
    if ctx.settings.eye_rest_enabled and not s.eye_pending:
        if s.eye.left_s is not None:
            s.eye.thaw(ctx.now)
        elif not s.eye.running:
            s.eye.start(ctx.settings.eye_rest_minutes * 60, ctx.now)
    if s.away_since is not None:  # started while away: hold until they're back
        s.focus.freeze(ctx.now)
        s.eye.freeze(ctx.now)


def _finish(ctx: _Ctx, outcome: str, feedback: Feedback | None = None) -> None:
    s = ctx.s
    _accrue_stop(s, ctx.now)
    if s.started_at is not None:
        ctx.record(
            type="focus",
            mode=s.mode,
            task=s.task,
            started_at=s.started_at,
            ended_at=ctx.now,
            planned_s=s.planned_s,
            active_s=int(s.active_s),
            extension_s=s.extension_s,
            outcome=outcome,
            feedback=feedback,
        )
    if feedback is not None and s.planned_s:
        _adapt(s, feedback, s.active_s / s.planned_s)
    adaptive, quiet = s.adaptive_focus_s, s.quiet_until
    hydration, pending = s.hydration, s.hydration_pending
    fresh = Session(adaptive_focus_s=adaptive, quiet_until=quiet, away_since=s.away_since)
    fresh.hydration, fresh.hydration_pending = hydration, pending
    for field in Session.model_fields:
        setattr(s, field, getattr(fresh, field))


def _adapt(s: Session, feedback: Feedback, completion: float) -> None:
    # A block abandoned early doesn't mean it was too short, so "too short"
    # only counts when most of it was actually spent focusing.
    if feedback is Feedback.TOO_SHORT and completion > 0.8:
        s.adaptive_focus_s = min(ADAPTIVE_MAX_S, s.adaptive_focus_s + ADAPTIVE_STEP_S)
    elif feedback is Feedback.TOO_LONG:
        s.adaptive_focus_s = max(ADAPTIVE_MIN_S, s.adaptive_focus_s - ADAPTIVE_STEP_S)


# -- due timers ------------------------------------------------------------------


def _fire_due(ctx: _Ctx, until: datetime | None = None) -> None:
    s, until = ctx.s, until or ctx.now
    handlers = (
        (s.focus, _on_focus_due),
        (s.rest, _on_rest_due),
        (s.hydration, _on_hydration_due),
        (s.eye, _on_eye_due),
    )
    # One at a time, earliest first: a handler may freeze or re-arm the others.
    while due := [(t.due_at, fn) for t, fn in handlers if t.due_at and t.due_at <= until]:
        due_at, fn = min(due, key=lambda item: item[0])
        fn(ctx, due_at)


def _on_focus_due(ctx: _Ctx, due_at: datetime) -> None:
    s = ctx.s
    s.focus.clear()
    _accrue_stop(s, due_at)
    s.eye.freeze(due_at)
    s.phase = Phase.RECOVERY_DUE
    hydration_left = s.hydration.remaining(ctx.now)
    if not ctx.settings.hydration_strict and (
        s.hydration_pending
        or (hydration_left is not None and hydration_left <= HYDRATION_MERGE_WINDOW_S)
    ):
        s.hydration_pending = True
    if s.hydration_pending and s.eye_pending:
        body = "Walk around, rest your eyes, and get some water."
    elif s.hydration_pending:
        body = "Walk around and get some water."
    elif s.eye_pending:
        body = "Walk around and rest your eyes."
    else:
        body = "Stand up and walk around for a few minutes."
    ctx.notify("Time for a reset.", body, "recovery")


def _on_rest_due(ctx: _Ctx, _due_at: datetime) -> None:
    ctx.s.rest.clear()
    if ctx.s.phase is Phase.BREAKING:
        ctx.notify("Break's up.", "Come back whenever you're ready.", "break_over")
    elif ctx.s.phase is Phase.IDEA_WALK:
        ctx.notify("Welcome back.", "Anything come to mind?", "idea_walk_over")


def _on_hydration_due(ctx: _Ctx, _due_at: datetime) -> None:
    s = ctx.s
    # Re-arm from now, not from the old due time, so a long gap produces one
    # reminder rather than a burst of catch-up ones.
    s.hydration.start(ctx.settings.hydration_minutes * 60, ctx.now)
    focus_left = s.focus.remaining(ctx.now) if s.phase is Phase.FOCUSING else None
    near_break = focus_left is not None and focus_left <= HYDRATION_MERGE_WINDOW_S
    in_break = s.phase in (Phase.RECOVERY_DUE, Phase.BREAKING)
    if not ctx.settings.hydration_strict and (near_break or in_break):
        s.hydration_pending = True  # folded into the (upcoming) break
        return
    ctx.notify("Hydration", "Time to drink some water.", "hydration")
    ctx.banner("💧 Time to drink some water.", "hydration")


def _on_eye_due(ctx: _Ctx, _due_at: datetime) -> None:
    # Eye rest is deliberately in-page only: a subtle prompt, never a system
    # notification that would break focus.
    ctx.s.eye.clear()
    ctx.s.eye_pending = True
    ctx.banner("👀 Look at something far away for 20 seconds.", "eye_rest")


# -- actions -----------------------------------------------------------------------


def _sync(ctx: _Ctx) -> None:
    """No-op: due timers have already fired by the time this runs."""


def _start(ctx: _Ctx) -> None:
    ctx.require(Phase.IDLE)
    s = ctx.s
    mode = Mode(ctx.payload.get("mode", Mode.ADAPTIVE))
    focus_s, recovery_s = DURATIONS.get(mode, (s.adaptive_focus_s, ADAPTIVE_RECOVERY_S))
    task = (ctx.payload.get("task") or "").strip()[:200] or None
    s.mode, s.task, s.started_at = mode, task, ctx.now
    s.planned_s, s.recovery_s = focus_s, recovery_s
    s.eye_pending = False
    s.eye.clear()
    _enter_focusing(ctx, focus_s)


def _pause(ctx: _Ctx) -> None:
    ctx.require(Phase.FOCUSING)
    s = ctx.s
    s.focus.freeze(ctx.now)
    s.eye.freeze(ctx.now)
    _accrue_stop(s, ctx.now)
    s.phase = Phase.PAUSED


def _resume(ctx: _Ctx) -> None:
    ctx.require(Phase.PAUSED)
    _enter_focusing(ctx, ctx.s.focus.left_s or 0)


def _extend(ctx: _Ctx) -> None:
    ctx.require(Phase.RECOVERY_DUE)
    s = ctx.s
    if s.extensions_used >= MAX_EXTENSIONS:
        raise InvalidAction("no extensions left for this block; time for a real break")
    s.extensions_used += 1
    s.extension_s += EXTENSION_S
    _enter_focusing(ctx, EXTENSION_S)


def _finish_thought(ctx: _Ctx) -> None:
    ctx.require(Phase.RECOVERY_DUE)
    if ctx.s.finish_thought_used:
        raise InvalidAction("already used this block")
    ctx.s.finish_thought_used = True
    _enter_focusing(ctx, FINISH_THOUGHT_S)


def _start_break(ctx: _Ctx) -> None:
    ctx.require(Phase.RECOVERY_DUE)
    s = ctx.s
    s.phase = Phase.BREAKING
    s.break_started_at = ctx.now
    s.rest.start(s.recovery_s, ctx.now)


def _feedback(ctx: _Ctx) -> Feedback | None:
    value = ctx.payload.get("feedback")
    return Feedback(value) if value else None


def _end_break(ctx: _Ctx) -> None:
    ctx.require(Phase.BREAKING)
    s = ctx.s
    if s.break_started_at is not None:
        ctx.record(
            type="break",
            kind="recovery",
            started_at=s.break_started_at,
            ended_at=ctx.now,
            seconds=int((ctx.now - s.break_started_at).total_seconds()),
            source="user",
        )
    if s.hydration_pending:
        # The break suggested water; assume it happened rather than re-nagging.
        s.hydration.start(ctx.settings.hydration_minutes * 60, ctx.now)
        s.hydration_pending = False
    _finish(ctx, "completed", _feedback(ctx))


def _skip_break(ctx: _Ctx) -> None:
    ctx.require(Phase.RECOVERY_DUE)
    ctx.record(type="break", kind="skipped", started_at=ctx.now, ended_at=ctx.now, seconds=0)
    _finish(ctx, "completed", _feedback(ctx))


def _idea_walk(ctx: _Ctx) -> None:
    ctx.require(Phase.FOCUSING)
    s = ctx.s
    s.focus.freeze(ctx.now)
    s.eye.freeze(ctx.now)
    s.hydration.freeze(ctx.now)
    _accrue_stop(s, ctx.now)
    s.phase = Phase.IDEA_WALK
    s.break_started_at = ctx.now
    s.rest.start(IDEA_WALK_S, ctx.now)


def _return(ctx: _Ctx) -> None:
    ctx.require(Phase.IDEA_WALK)
    s = ctx.s
    note = (ctx.payload.get("note") or "").strip()[:2000]
    if note:
        ctx.record(type="note", at=ctx.now, text=note)
    if s.break_started_at is not None:
        ctx.record(
            type="break",
            kind="idea_walk",
            started_at=s.break_started_at,
            ended_at=ctx.now,
            seconds=int((ctx.now - s.break_started_at).total_seconds()),
            source="user",
        )
    s.rest.clear()
    s.break_started_at = None
    s.hydration.thaw(ctx.now)
    if ctx.payload.get("resume", True):
        _enter_focusing(ctx, s.focus.left_s or 0)
    else:
        _finish(ctx, "interrupted")


def _stop(ctx: _Ctx) -> None:
    if ctx.s.phase is Phase.IDLE:
        return
    if ctx.s.phase is Phase.IDEA_WALK:
        ctx.s.hydration.thaw(ctx.now)
    _finish(ctx, "abandoned")


def _away(ctx: _Ctx) -> None:
    s = ctx.s
    if s.away_since is not None:
        return
    since = _since(ctx)
    _fire_due(ctx, until=since)  # deadlines that passed before they left still count
    s.away_since = since
    _accrue_stop(s, since)
    if s.phase is Phase.FOCUSING:
        s.focus.freeze(since)
        s.eye.freeze(since)
    if s.phase is not Phase.IDEA_WALK:  # an idea walk already froze hydration
        s.hydration.freeze(since)


def _back(ctx: _Ctx) -> None:
    s = ctx.s
    if s.away_since is None:
        if "since" not in ctx.payload:
            return
        _away(ctx)  # a gap the page noticed after the fact (sleep, closed tab)
    since = s.away_since
    assert since is not None
    away_s = (ctx.now - since).total_seconds()
    s.away_since = None
    if s.phase is Phase.FOCUSING:
        s.focus.thaw(ctx.now)
        s.eye.thaw(ctx.now)
        _accrue_start(s, ctx.now)
    if s.phase is not Phase.IDEA_WALK:
        s.hydration.thaw(ctx.now)

    if s.phase in (Phase.BREAKING, Phase.IDEA_WALK) or away_s < AWAY_COUNTS_AS_BREAK_S:
        return
    ctx.record(
        type="break",
        kind="away",
        started_at=since,
        ended_at=ctx.now,
        seconds=int(away_s),
        source="idle_detected",
    )
    # Stepping away when a break was due *is* the break, so don't ask for
    # another one on return.
    if s.phase is Phase.RECOVERY_DUE and away_s >= s.recovery_s:
        if s.hydration_pending:
            s.hydration.start(ctx.settings.hydration_minutes * 60, ctx.now)
            s.hydration_pending = False
        _finish(ctx, "completed")
        ctx.banner("Welcome back. That counted as your break.", "welcome_back")


def _since(ctx: _Ctx) -> datetime:
    raw = ctx.payload.get("since")
    if raw is None:
        return ctx.now
    since = raw if isinstance(raw, datetime) else datetime.fromisoformat(raw)
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    return min(since, ctx.now)


def _drink(ctx: _Ctx) -> None:
    s = ctx.s
    ctx.record(type="drink", at=ctx.now)
    s.hydration_pending = False
    if s.hydration.running:
        s.hydration.start(ctx.settings.hydration_minutes * 60, ctx.now)
    else:
        s.hydration.left_s = ctx.settings.hydration_minutes * 60


def _dismiss(ctx: _Ctx) -> None:
    s = ctx.s
    if s.eye_pending:
        s.eye_pending = False
        if ctx.settings.eye_rest_enabled and s.phase is Phase.FOCUSING:
            s.eye.start(ctx.settings.eye_rest_minutes * 60, ctx.now)


def _quiet(ctx: _Ctx) -> None:
    minutes = ctx.payload.get("minutes", ctx.settings.quiet_minutes)
    minutes = max(0, min(240, int(minutes)))
    ctx.s.quiet_until = ctx.now + timedelta(minutes=minutes) if minutes else None


_ACTIONS = {
    "sync": _sync,
    "start": _start,
    "pause": _pause,
    "resume": _resume,
    "extend": _extend,
    "finish_thought": _finish_thought,
    "start_break": _start_break,
    "end_break": _end_break,
    "skip_break": _skip_break,
    "idea_walk": _idea_walk,
    "return": _return,
    "stop": _stop,
    "away": _away,
    "back": _back,
    "drink": _drink,
    "dismiss": _dismiss,
    "quiet": _quiet,
}
ACTIONS = frozenset(_ACTIONS)
