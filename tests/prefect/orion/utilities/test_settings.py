import json
import os
import prefect.orion


def test_settings():
    settings = prefect.orion.Settings()
    assert settings.test_mode is True


def test_runtime_settings():
    settings = prefect.orion.Settings()
    assert settings.test_mode is True

    os.environ["ORION_TEST_MODE"] = "0"
    settings = prefect.orion.Settings()
    assert settings.test_mode is False


def test_nested_settings():
    os.environ["ORION_DATABASE_ECHO"] = "1"
    settings = prefect.orion.Settings()
    assert settings.database.echo is True

    os.environ["ORION_DATABASE_ECHO"] = "0"
    settings = prefect.orion.Settings()
    assert settings.database.echo is False


def test_secret_settings_are_not_serialized():
    settings = prefect.orion.Settings()
    assert settings.database.connection_url != "**********"

    settings_json = json.loads(settings.json())
    assert settings_json["database"]["connection_url"] == "**********"
