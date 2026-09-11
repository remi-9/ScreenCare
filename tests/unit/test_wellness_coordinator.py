from screencare.engines.hydration_engine import HydrationSettings
from screencare.engines.wellness_coordinator import WellnessCoordinator


def test_hydration_due_shortly_before_the_break_is_merged_into_it() -> None:
    """The worked example from ScreenCare — Technical.md section 7:
    hydration due in 2 minutes, recovery break due in 6 minutes -> one
    combined recovery event 6 minutes from now, not a separate hydration
    ping first.
    """
    coordinator = WellnessCoordinator(HydrationSettings(merge_window_seconds=10 * 60))
    decision = coordinator.decide_recovery(
        recovery_due_in_seconds=6 * 60,
        hydration_due_in_seconds=2 * 60,
        eye_rest_overdue=False,
    )
    assert decision.fire_in_seconds == 6 * 60
    assert decision.include_hydration is True


def test_hydration_due_far_before_the_break_is_not_merged() -> None:
    # Gap between hydration and the break exceeds the merge window.
    coordinator = WellnessCoordinator(HydrationSettings(merge_window_seconds=10 * 60))
    decision = coordinator.decide_recovery(
        recovery_due_in_seconds=45 * 60,
        hydration_due_in_seconds=2 * 60,
        eye_rest_overdue=False,
    )
    assert decision.include_hydration is False


def test_hydration_due_after_the_break_is_not_merged_into_it() -> None:
    # The break comes first; hydration isn't due yet, so nothing to merge.
    coordinator = WellnessCoordinator(HydrationSettings(merge_window_seconds=10 * 60))
    decision = coordinator.decide_recovery(
        recovery_due_in_seconds=5 * 60,
        hydration_due_in_seconds=20 * 60,
        eye_rest_overdue=False,
    )
    assert decision.include_hydration is False


def test_strict_hydration_mode_never_merges() -> None:
    coordinator = WellnessCoordinator(HydrationSettings(merge_window_seconds=10 * 60, strict=True))
    decision = coordinator.decide_recovery(
        recovery_due_in_seconds=6 * 60,
        hydration_due_in_seconds=2 * 60,
        eye_rest_overdue=False,
    )
    assert decision.include_hydration is False


def test_no_hydration_due_time_means_no_hydration_in_the_decision() -> None:
    coordinator = WellnessCoordinator()
    decision = coordinator.decide_recovery(
        recovery_due_in_seconds=6 * 60,
        hydration_due_in_seconds=None,
        eye_rest_overdue=True,
    )
    assert decision.include_hydration is False
    assert decision.include_eye_rest is True


def test_hydration_fires_standalone_once_due_with_no_break_nearby() -> None:
    coordinator = WellnessCoordinator(HydrationSettings(merge_window_seconds=10 * 60))
    assert coordinator.should_fire_hydration_standalone(
        hydration_due_in_seconds=0,
        recovery_due_in_seconds=45 * 60,
    )


def test_hydration_does_not_fire_standalone_if_not_yet_due() -> None:
    coordinator = WellnessCoordinator()
    assert not coordinator.should_fire_hydration_standalone(
        hydration_due_in_seconds=30,
        recovery_due_in_seconds=None,
    )


def test_hydration_does_not_fire_standalone_when_it_will_be_merged() -> None:
    coordinator = WellnessCoordinator(HydrationSettings(merge_window_seconds=10 * 60))
    assert not coordinator.should_fire_hydration_standalone(
        hydration_due_in_seconds=0,
        recovery_due_in_seconds=5 * 60,
    )


def test_strict_mode_always_fires_hydration_standalone_once_due() -> None:
    coordinator = WellnessCoordinator(HydrationSettings(merge_window_seconds=10 * 60, strict=True))
    assert coordinator.should_fire_hydration_standalone(
        hydration_due_in_seconds=0,
        recovery_due_in_seconds=5 * 60,
    )
