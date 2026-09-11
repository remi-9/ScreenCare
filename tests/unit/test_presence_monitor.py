"""``PresenceMonitor`` -- entirely Qt-free and platform-free, so every
branch of the idle/lock/sleep decision table (``ScreenCare — Technical.md``
section 13) is testable with a fake ``ActivityProvider``.
"""

from __future__ import annotations

from screencare.activity.presence_monitor import PresenceMonitor
from screencare.domain.enums import PresenceState


class _FakeActivityProvider:
    def __init__(self, *, idle_seconds: float = 0.0, locked: bool = False) -> None:
        self.idle_seconds_value = idle_seconds
        self.locked = locked

    def idle_seconds(self) -> float:
        return self.idle_seconds_value

    def is_locked(self) -> bool:
        return self.locked


class _FailingActivityProvider:
    def idle_seconds(self) -> float:
        raise OSError("boom")

    def is_locked(self) -> bool:
        return False


def test_no_provider_is_always_active() -> None:
    monitor = PresenceMonitor(provider=None)
    assert monitor.poll() is PresenceState.ACTIVE


def test_below_threshold_is_active() -> None:
    provider = _FakeActivityProvider(idle_seconds=10)
    monitor = PresenceMonitor(provider=provider, idle_threshold_seconds=90)
    assert monitor.poll() is PresenceState.ACTIVE


def test_at_or_above_threshold_is_idle() -> None:
    provider = _FakeActivityProvider(idle_seconds=90)
    monitor = PresenceMonitor(provider=provider, idle_threshold_seconds=90)
    assert monitor.poll() is PresenceState.IDLE


def test_locked_overrides_idle_seconds() -> None:
    provider = _FakeActivityProvider(idle_seconds=0, locked=True)
    monitor = PresenceMonitor(provider=provider)
    assert monitor.poll() is PresenceState.LOCKED


def test_sleeping_overrides_everything_until_marked_awake() -> None:
    provider = _FakeActivityProvider(idle_seconds=0, locked=False)
    monitor = PresenceMonitor(provider=provider)
    monitor.mark_sleeping()
    assert monitor.poll() is PresenceState.SLEEPING

    monitor.mark_awake()
    assert monitor.poll() is PresenceState.ACTIVE


def test_a_failing_provider_is_disabled_and_never_raises() -> None:
    monitor = PresenceMonitor(provider=_FailingActivityProvider())
    assert monitor.poll() is PresenceState.ACTIVE  # degrades, doesn't raise
    assert monitor.poll() is PresenceState.ACTIVE  # stays degraded


def test_set_provider_clears_the_failed_latch() -> None:
    monitor = PresenceMonitor(provider=_FailingActivityProvider())
    monitor.poll()  # trips the failure latch

    monitor.set_provider(_FakeActivityProvider(idle_seconds=0))
    assert monitor.poll() is PresenceState.ACTIVE
