import json
import os

from prefect import settings
from prefect.utilities.settings import Settings


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
