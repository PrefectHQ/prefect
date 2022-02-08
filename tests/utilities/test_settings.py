import os
import pytest

import prefect.settings
from prefect.settings import Settings, LoggingSettings
from prefect.utilities.testing import temporary_settings


def test_settings():
    assert prefect.settings.from_env().test_mode is True

def test_temporary_settings():
    assert prefect.settings.from_env().test_mode is True
    with temporary_settings(PREFECT_TEST_MODE=False) as new_settings:
        assert new_settings.test_mode is False, "Yields the new settings"
        assert prefect.settings.from_env().test_mode is False, "Loading from env works"

    assert prefect.settings.from_env().test_mode is True, "Restores old setting"

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
