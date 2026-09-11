import pytest

from screencare.persistence.settings import AppSettings, InMemorySettingsBackend


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(InMemorySettingsBackend())


def test_defaults_are_sensible(settings: AppSettings) -> None:
    assert settings.focus_minutes == 25
    assert settings.short_break_minutes == 5
    assert settings.hydration_interval_minutes == 60
    assert settings.hydration_strict is False
    assert settings.eye_reminder_minutes == 20
    assert settings.eye_reminder_enabled is True
    assert settings.quiet_mode_minutes == 60
    assert settings.notifications_enabled is True
    assert settings.sound_enabled is True
    assert settings.launch_at_login is False
    assert settings.onboarding_completed is False
    assert settings.theme == "system"


def test_setting_a_value_within_bounds_round_trips(settings: AppSettings) -> None:
    settings.focus_minutes = 45
    assert settings.focus_minutes == 45


@pytest.mark.parametrize(
    ("attr", "too_low", "too_high", "lo", "hi"),
    [
        ("focus_minutes", 1, 999, 10, 120),
        ("short_break_minutes", 0, 999, 1, 30),
        ("hydration_interval_minutes", 5, 999, 30, 180),
        ("eye_reminder_minutes", 1, 999, 10, 60),
        ("quiet_mode_minutes", 1, 999, 15, 240),
    ],
)
def test_out_of_range_values_are_clamped_on_write(
    settings: AppSettings, attr: str, too_low: int, too_high: int, lo: int, hi: int
) -> None:
    setattr(settings, attr, too_low)
    assert getattr(settings, attr) == lo
    setattr(settings, attr, too_high)
    assert getattr(settings, attr) == hi


def test_a_corrupted_stored_value_falls_back_to_the_default(settings: AppSettings) -> None:
    # Simulate a QSettings file hand-edited or corrupted by something else.
    settings._backend.set_value("focus/duration_minutes", "not-a-number")
    assert settings.focus_minutes == 25


def test_an_out_of_range_value_written_directly_to_the_backend_is_clamped_on_read() -> None:
    backend = InMemorySettingsBackend()
    backend.set_value("focus/duration_minutes", 99999)
    settings = AppSettings(backend)
    assert settings.focus_minutes == 120


def test_bool_settings_round_trip() -> None:
    settings = AppSettings(InMemorySettingsBackend())
    settings.notifications_enabled = False
    assert settings.notifications_enabled is False
    settings.notifications_enabled = True
    assert settings.notifications_enabled is True


def test_bool_settings_tolerate_string_backed_storage() -> None:
    # Some QSettings backends (INI format) round-trip bools as strings.
    backend = InMemorySettingsBackend()
    backend.set_value("notifications/enabled", "false")
    settings = AppSettings(backend)
    assert settings.notifications_enabled is False


def test_theme_accepts_only_known_values(settings: AppSettings) -> None:
    settings.theme = "dark"
    assert settings.theme == "dark"
    with pytest.raises(ValueError):
        settings.theme = "psychedelic"


def test_an_unknown_stored_theme_falls_back_to_system() -> None:
    backend = InMemorySettingsBackend()
    backend.set_value("app/theme", "psychedelic")
    settings = AppSettings(backend)
    assert settings.theme == "system"
