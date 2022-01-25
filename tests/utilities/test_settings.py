import pytest
import json
import os

from prefect import settings
from prefect.utilities.settings import Settings, temporary_settings, LoggingSettings


def test_settings():
    assert settings.test_mode is True


def test_refresh_settings():
    assert settings.test_mode is True

    os.environ["PREFECT_TEST_MODE"] = "0"
    new_settings = Settings()
    assert new_settings.test_mode is False


def test_nested_settings():
    assert settings.orion.database.echo is False

    os.environ["PREFECT_ORION_DATABASE_ECHO"] = "1"
    new_settings = Settings()
    assert new_settings.orion.database.echo is True


def test_secret_settings_are_not_serialized():
    assert settings.orion.database.connection_url != "**********"

    settings_json = json.loads(settings.json())
    assert settings_json["orion"]["database"]["connection_url"] == "**********"


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
