from unittest.mock import MagicMock

import pytest
import yaml

from prefect.utilities.logging import (
    DEFAULT_LOGGING_SETTINGS_PATH,
    get_logger,
    setup_logging,
    load_logging_config,
)
from prefect.utilities.settings import LoggingSettings, Settings
from prefect import settings


@pytest.fixture
def dictConfigMock(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("logging.config.dictConfig", mock)
    return mock


def test_setup_logging_uses_default_path(tmp_path, dictConfigMock):
    fake_settings = Settings(
        logging=LoggingSettings(settings_path=tmp_path.joinpath("does-not-exist.yaml"))
    )

    expected_config = load_logging_config(
        DEFAULT_LOGGING_SETTINGS_PATH, fake_settings.logging
    )

    setup_logging(fake_settings)

    dictConfigMock.assert_called_once_with(expected_config)


def test_setup_logging_uses_settings_path_if_exists(tmp_path, dictConfigMock):
    config_file = tmp_path.joinpath("exists.yaml")
    config_file.write_text("foo: bar")
    fake_settings = Settings(logging=LoggingSettings(settings_path=config_file))

    setup_logging(fake_settings)
    expected_config = load_logging_config(
        tmp_path.joinpath("exists.yaml"), fake_settings.logging
    )

    dictConfigMock.assert_called_once_with(expected_config)


def test_setup_logging_uses_env_var_overrides(tmp_path, dictConfigMock, monkeypatch):
    fake_settings = Settings(
        logging=LoggingSettings(settings_path=tmp_path.joinpath("does-not-exist.yaml"))
    )
    expected_config = load_logging_config(
        DEFAULT_LOGGING_SETTINGS_PATH, fake_settings.logging
    )

    # Test setting a simple value
    monkeypatch.setenv(
        LoggingSettings.Config.env_prefix + "LOGGERS_ROOT_LEVEL", "ROOT_LEVEL_VAL"
    )
    expected_config["loggers"]["root"]["level"] = "ROOT_LEVEL_VAL"

    # Test setting a value where the a key contains underscores
    monkeypatch.setenv(
        LoggingSettings.Config.env_prefix + "FILTERS_RUN_CONTEXT_CLASS",
        "UNDERSCORE_KEY_VAL",
    )
    expected_config["filters"]["run_context"]["class"] = "UNDERSCORE_KEY_VAL"

    # Test setting a value where the key contains a period
    monkeypatch.setenv(
        LoggingSettings.Config.env_prefix + "LOGGERS_PREFECT_FLOW_RUN_LEVEL",
        "FLOW_RUN_VAL",
    )
    expected_config["loggers"]["prefect.flow_run"]["level"] = "FLOW_RUN_VAL"

    # Test setting a value that does not exist in the yaml config and should not be
    # set in the expected_config since there is no value to override
    monkeypatch.setenv(LoggingSettings.Config.env_prefix + "_FOO", "IGNORED")

    setup_logging(fake_settings)

    dictConfigMock.assert_called_once_with(expected_config)


@pytest.mark.parametrize("name", ["default", None, ""])
def test_get_logger_returns_prefect_logger_by_default(name):
    if name == "default":
        logger = get_logger()
    else:
        logger = get_logger(name)

    assert logger.name == "prefect"


def test_get_logger_returns_prefect_child_logger():
    logger = get_logger("foo")
    assert logger.name == "prefect.foo"


def test_default_level_is_applied_to_interpolated_yaml_values(dictConfigMock):
    fake_settings = Settings(logging=LoggingSettings(default_level="WARNING"))

    expected_config = load_logging_config(
        DEFAULT_LOGGING_SETTINGS_PATH, fake_settings.logging
    )

    assert expected_config["handlers"]["console"]["level"] == "WARNING"
    assert expected_config["handlers"]["orion"]["level"] == "WARNING"

    setup_logging(fake_settings)
    dictConfigMock.assert_called_once_with(expected_config)
