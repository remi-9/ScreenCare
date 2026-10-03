from datetime import UTC, datetime, timedelta

from screencare import messages as msg

T0 = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)


def test_recovery_bodies_only_mention_what_the_break_includes():
    for (water, eyes), bodies in msg.RECOVERY_BODIES.items():
        for body in bodies:
            assert ("water" in body) == water, body
            if eyes:
                assert "eye" in body or "far away" in body, body


def test_pick_is_deterministic_for_a_moment_but_varies_over_time():
    assert msg.pick(msg.EYE_REST, T0) == msg.pick(msg.EYE_REST, T0)
    seen = {msg.pick(msg.EYE_REST, T0 + timedelta(minutes=m)) for m in range(60)}
    assert len(seen) > 1


def test_copy_keeps_the_tone():
    texts = [*msg.RECOVERY_TITLES, *msg.EYE_REST, *msg.WELCOME_BACK, *msg.HYDRATION_BODIES]
    texts += [t for bodies in msg.RECOVERY_BODIES.values() for t in bodies]
    for entry in msg.UI.values():
        for item in entry:
            texts += list(item) if isinstance(item, tuple) else [item]
    for text in texts:
        assert "!" not in text, text  # calm, never shouty


def test_every_screen_has_variants():
    for key in (
        "idle",
        "focusing",
        "overtime",
        "paused",
        "recovery",
        "postponed",
        "postponed_max",
        "breaking",
        "idea_walk",
        "drink",
    ):
        assert len(msg.UI[key]) >= 3, key
