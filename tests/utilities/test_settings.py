import os

import pytest

import prefect.settings
from prefect.settings import LoggingSettings, Settings
from prefect.utilities.testing import temporary_settings


def test_settings():
    assert prefect.settings.from_env().test_mode is True


def test_temporary_settings():
    assert prefect.settings.from_env().test_mode is True
    with temporary_settings(PREFECT_TEST_MODE=False) as new_settings:
        assert new_settings.test_mode is False, "Yields the new settings"
        assert prefect.settings.from_env().test_mode is False, "Loads from env"
        assert prefect.settings.from_context().test_mode is False, "Loads from context"

    assert prefect.settings.from_env().test_mode is True, "Restores old setting"
    assert prefect.settings.from_context().test_mode is True, "Restores old profile"


def test_temporary_settings_restores_on_error():
    assert prefect.settings.from_env().test_mode is True

    with pytest.raises(ValueError):
        with temporary_settings(PREFECT_TEST_MODE=False):
            raise ValueError()

    assert os.environ["PREFECT_TEST_MODE"] == "1", "Restores os environ."
    assert prefect.settings.from_env().test_mode is True, "Restores old setting"
    assert prefect.settings.from_context().test_mode is True, "Restores old profile"


def test_refresh_settings():
    assert prefect.settings.from_env().test_mode is True

    os.environ["PREFECT_TEST_MODE"] = "0"
    new_settings = Settings()
    assert new_settings.test_mode is False


def test_nested_settings():
    assert prefect.settings.from_env().orion.database.echo is False

    os.environ["PREFECT_ORION_DATABASE_ECHO"] = "1"
    new_settings = Settings()
    assert new_settings.orion.database.echo is True


@pytest.mark.parametrize(
    "value,expected",
    [
        ("foo", ["foo"]),
        ("foo,bar", ["foo", "bar"]),
        ("foo, bar, foobar ", ["foo", "bar", "foobar"]),
    ],
)
def test_extra_loggers(value, expected):
    settings = LoggingSettings(extra_loggers=value)
    assert settings.get_extra_loggers() == expected
