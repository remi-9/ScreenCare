import pytest

from screencare.domain.enums import FocusFeedback
from screencare.engines.adaptive_focus import AdaptiveFocusBounds, AdaptiveFocusEngine


def test_too_short_with_high_completion_increases_duration() -> None:
    engine = AdaptiveFocusEngine(initial_seconds=25 * 60)
    new_duration = engine.record_outcome(feedback=FocusFeedback.TOO_SHORT, completion_rate=0.9)
    assert new_duration == 30 * 60
    assert engine.current_duration_seconds == 30 * 60


def test_too_short_with_low_completion_does_not_increase_duration() -> None:
    # A session abandoned early isn't evidence it was too short.
    engine = AdaptiveFocusEngine(initial_seconds=25 * 60)
    new_duration = engine.record_outcome(feedback=FocusFeedback.TOO_SHORT, completion_rate=0.5)
    assert new_duration == 25 * 60


def test_too_long_always_decreases_duration() -> None:
    engine = AdaptiveFocusEngine(initial_seconds=25 * 60)
    new_duration = engine.record_outcome(feedback=FocusFeedback.TOO_LONG, completion_rate=1.0)
    assert new_duration == 20 * 60


def test_just_right_leaves_duration_unchanged() -> None:
    engine = AdaptiveFocusEngine(initial_seconds=25 * 60)
    new_duration = engine.record_outcome(feedback=FocusFeedback.JUST_RIGHT, completion_rate=1.0)
    assert new_duration == 25 * 60


def test_duration_never_exceeds_the_maximum_bound() -> None:
    engine = AdaptiveFocusEngine(initial_seconds=55 * 60)
    engine.record_outcome(feedback=FocusFeedback.TOO_SHORT, completion_rate=1.0)
    assert engine.current_duration_seconds == 60 * 60
    # A further increase must not push it past the cap.
    engine.record_outcome(feedback=FocusFeedback.TOO_SHORT, completion_rate=1.0)
    assert engine.current_duration_seconds == 60 * 60


def test_duration_never_drops_below_the_minimum_bound() -> None:
    engine = AdaptiveFocusEngine(initial_seconds=22 * 60)
    engine.record_outcome(feedback=FocusFeedback.TOO_LONG, completion_rate=1.0)
    assert engine.current_duration_seconds == 20 * 60
    engine.record_outcome(feedback=FocusFeedback.TOO_LONG, completion_rate=1.0)
    assert engine.current_duration_seconds == 20 * 60


def test_initial_duration_outside_bounds_is_clamped_on_construction() -> None:
    engine = AdaptiveFocusEngine(initial_seconds=5 * 60)
    assert engine.current_duration_seconds == 20 * 60


def test_custom_bounds_are_respected() -> None:
    bounds = AdaptiveFocusBounds(
        minimum_seconds=10 * 60, maximum_seconds=15 * 60, step_seconds=10 * 60
    )
    engine = AdaptiveFocusEngine(initial_seconds=10 * 60, bounds=bounds)
    engine.record_outcome(feedback=FocusFeedback.TOO_SHORT, completion_rate=1.0)
    assert engine.current_duration_seconds == 15 * 60  # clamped, not 20 min


def test_bounds_reject_a_minimum_above_the_maximum() -> None:
    with pytest.raises(ValueError):
        AdaptiveFocusBounds(minimum_seconds=100, maximum_seconds=50)


def test_bounds_reject_non_positive_values() -> None:
    with pytest.raises(ValueError):
        AdaptiveFocusBounds(minimum_seconds=0)
