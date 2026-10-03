from datetime import UTC, datetime, timedelta

import pytest

from screencare.rules import (
    ADAPTIVE_MAX_S,
    InvalidAction,
    Phase,
    Session,
    Settings,
    apply,
)

T0 = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)


class Sim:
    """Drives `apply` the way the browser does, with a hand-moved clock."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.now = T0
        self.session = Session()
        self.settings = settings or Settings()
        self.events: list[dict] = []
        self.history: list[dict] = []
        self.do("sync")  # the page syncs on load, which arms hydration

    def do(self, action: str, **payload) -> list[dict]:
        self.session, self.events = apply(self.session, self.settings, action, payload, self.now)
        self.history += [e for e in self.events if e["event"] == "record"]
        return self.events

    def wait(self, minutes: float = 0, seconds: float = 0) -> list[dict]:
        self.now += timedelta(minutes=minutes, seconds=seconds)
        return self.do("sync")

    def at(self, minutes: float) -> datetime:
        return self.now + timedelta(minutes=minutes)

    def kinds(self, events=None) -> list[str]:
        return [e.get("type") for e in (events if events is not None else self.events)]

    def records(self, type_: str) -> list[dict]:
        return [r for r in self.history if r["type"] == type_]


def test_classic_block_runs_to_recovery_and_records_completion():
    sim = Sim()
    sim.do("start", mode="classic", task="Auth flow")
    assert sim.session.phase is Phase.FOCUSING
    sim.wait(minutes=24)
    assert sim.session.phase is Phase.FOCUSING
    sim.wait(minutes=1)
    assert sim.session.phase is Phase.RECOVERY_DUE
    assert "recovery" in sim.kinds()

    sim.do("start_break")
    sim.wait(minutes=5)
    sim.do("end_break", feedback="just_right")
    assert sim.session.phase is Phase.IDLE
    (focus,) = sim.records("focus")
    assert focus["outcome"] == "completed"
    assert focus["active_s"] == 25 * 60
    assert focus["task"] == "Auth flow"
    assert sim.records("break")[0]["seconds"] == 5 * 60


def test_sleeping_mid_session_is_not_counted_as_focus():
    sim = Sim()
    sim.do("start", mode="classic")
    sim.wait(minutes=10)
    went_to_sleep = sim.now
    sim.now += timedelta(minutes=30)  # laptop asleep: no requests at all
    sim.do("back", since=went_to_sleep.isoformat())

    assert sim.session.phase is Phase.FOCUSING
    assert sim.session.focus.remaining(sim.now) == pytest.approx(15 * 60)
    assert sim.session.active_s == pytest.approx(10 * 60)
    away = sim.records("break")[0]
    assert away["kind"] == "away" and away["source"] == "idle_detected"
    assert away["seconds"] == 30 * 60


def test_timestamp_without_timezone_is_treated_as_utc():
    sim = Sim()
    sim.do("start", mode="classic")
    sim.wait(minutes=5)
    sim.do("away", since=sim.now.replace(tzinfo=None).isoformat())
    assert sim.session.away_since == sim.now


def test_short_absence_is_not_a_break():
    sim = Sim()
    sim.do("start", mode="classic")
    sim.do("away")
    sim.wait(minutes=2)
    sim.do("back")
    assert sim.records("break") == []
    assert sim.session.focus.remaining(sim.now) == pytest.approx(25 * 60)


def test_deadline_before_leaving_still_fires_with_exact_active_time():
    sim = Sim()
    sim.do("start", mode="classic")
    sim.now += timedelta(minutes=31)  # block ended at 25; the laptop slept at 30
    sim.do("back", since=(T0 + timedelta(minutes=30)).isoformat())
    assert sim.session.phase is Phase.RECOVERY_DUE
    assert sim.session.active_s == pytest.approx(25 * 60)


def test_walking_away_when_break_is_due_counts_as_the_break():
    sim = Sim()
    sim.do("start", mode="classic")
    sim.wait(minutes=25)
    sim.do("away")
    sim.wait(minutes=6)
    events = sim.do("back")
    assert sim.session.phase is Phase.IDLE
    assert sim.records("focus")[0]["outcome"] == "completed"
    assert "welcome_back" in sim.kinds(events)


NO_EYE = Settings(eye_rest_enabled=False)


def test_hydration_close_to_break_merges_into_it():
    sim = Sim(NO_EYE)
    sim.wait(minutes=30)  # hydration due at 60 min
    sim.do("start", mode="classic")  # recovery due at 55 min
    events = sim.wait(minutes=25)
    assert sim.session.phase is Phase.RECOVERY_DUE
    assert sim.kinds(events) == ["recovery"]  # one intervention, not two
    assert "water" in events[0]["body"]
    sim.wait(minutes=5)  # hydration's own due time passes during recovery
    assert "hydration" not in sim.kinds()


def test_hydration_far_from_break_fires_on_its_own():
    sim = Sim(NO_EYE)
    sim.wait(minutes=50)
    sim.do("start", mode="deep")
    events = sim.wait(minutes=10)
    assert sim.session.phase is Phase.FOCUSING
    assert "hydration" in sim.kinds(events)


def test_strict_hydration_never_merges():
    sim = Sim(Settings(hydration_strict=True, eye_rest_enabled=False))
    sim.wait(minutes=30)
    sim.do("start", mode="classic")
    sim.wait(minutes=25)
    assert "water" not in sim.events[0]["body"]
    assert "hydration" in sim.kinds(sim.wait(minutes=5))


def test_extensions_are_limited():
    sim = Sim()
    sim.do("start", mode="classic")
    sim.wait(minutes=25)
    for _ in range(2):
        sim.do("extend")
        sim.wait(minutes=5)
        assert sim.session.phase is Phase.RECOVERY_DUE
    with pytest.raises(InvalidAction):
        sim.do("extend")
    sim.do("finish_thought")
    sim.wait(minutes=2)
    with pytest.raises(InvalidAction):
        sim.do("finish_thought")
    sim.do("start_break")
    sim.do("end_break")
    assert sim.records("focus")[0]["extension_s"] == 10 * 60


def test_eye_rest_is_in_page_only_and_rearms_after_dismiss():
    sim = Sim(Settings(eye_rest_minutes=10))
    sim.do("start", mode="deep")
    events = sim.wait(minutes=10)
    assert [e["event"] for e in events] == ["banner"]
    assert sim.kinds(events) == ["eye_rest"]
    assert sim.wait(minutes=10) == []  # waits for acknowledgement instead of stacking
    sim.do("dismiss")
    assert sim.kinds(sim.wait(minutes=10)) == ["eye_rest"]


def test_pause_freezes_everything_focus_related():
    sim = Sim()
    sim.do("start", mode="classic")
    sim.wait(minutes=5)
    sim.do("pause")
    sim.wait(minutes=60)
    assert sim.session.phase is Phase.PAUSED
    sim.do("resume")
    sim.wait(minutes=19)
    assert sim.session.phase is Phase.FOCUSING
    sim.wait(minutes=1)
    assert sim.session.phase is Phase.RECOVERY_DUE


def test_idea_walk_freezes_focus_and_captures_note():
    sim = Sim()
    sim.do("start", mode="classic")
    sim.wait(minutes=10)
    sim.do("idea_walk")
    events = sim.wait(minutes=5)
    assert "idea_walk_over" in sim.kinds(events)
    sim.wait(minutes=3)
    sim.do("return", note="Try a token bucket")
    assert sim.session.phase is Phase.FOCUSING
    assert sim.session.focus.remaining(sim.now) == pytest.approx(15 * 60)
    assert sim.records("note")[0]["text"] == "Try a token bucket"
    assert sim.records("break")[0]["kind"] == "idea_walk"


def test_adaptive_feedback_tunes_next_duration_within_bounds():
    sim = Sim()
    for _ in range(10):
        sim.do("start", mode="adaptive")
        sim.wait(seconds=sim.session.planned_s)
        sim.do("start_break")
        sim.do("end_break", feedback="too_short")
    assert sim.session.adaptive_focus_s == ADAPTIVE_MAX_S

    sim.do("start", mode="adaptive")
    sim.wait(minutes=1)
    sim.do("stop")
    before = sim.session.adaptive_focus_s
    sim.do("start", mode="adaptive")
    sim.wait(minutes=60)
    sim.do("skip_break", feedback="too_long")
    assert sim.session.adaptive_focus_s == before - 5 * 60


def test_quiet_mode_suppresses_messages_not_timers():
    sim = Sim()
    sim.do("quiet", minutes=60)
    sim.do("start", mode="classic")
    assert sim.wait(minutes=25) == []
    assert sim.session.phase is Phase.RECOVERY_DUE


def test_invalid_transitions_raise():
    sim = Sim()
    with pytest.raises(InvalidAction):
        sim.do("pause")
    with pytest.raises(InvalidAction):
        sim.do("nonsense")


def test_settings_are_clamped_not_rejected():
    s = Settings(hydration_minutes=1, eye_rest_minutes=999)
    assert (s.hydration_minutes, s.eye_rest_minutes) == (30, 60)


def test_session_round_trips_through_json():
    sim = Sim()
    sim.do("start", mode="deep", task="Write")
    sim.wait(minutes=3)
    restored = Session.model_validate_json(sim.session.model_dump_json())
    assert restored == sim.session
