import yaml
import os
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from prefect.utilities.logging import (
    get_logger,
    setup_logging,
    DEFAULT_LOGGING_SETTINGS_PATH,
)
from prefect.utilities.settings import Settings, LoggingSettings


@pytest.fixture
def dictConfigMock(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("logging.config.dictConfig", mock)
    return mock


def test_setup_logging_uses_default_path(tmpdir, dictConfigMock):
    fake_settings = Settings(
        logging=LoggingSettings(settings_path=tmpdir.join("does-not-exist.yaml"))
    )

    setup_logging(fake_settings)

    dictConfigMock.assert_called_once_with(
        yaml.safe_load(DEFAULT_LOGGING_SETTINGS_PATH.read_text())
    )


def test_setup_logging_uses_settings_path_if_exists(tmpdir, dictConfigMock):
    config_path = tmpdir.join("exists.yaml")
    config_path.write(DEFAULT_LOGGING_SETTINGS_PATH.read_text())
    fake_settings = Settings(logging=LoggingSettings(settings_path=config_path))

    setup_logging(fake_settings)

    dictConfigMock.assert_called_once_with(
        yaml.safe_load(DEFAULT_LOGGING_SETTINGS_PATH.read_text())
    )


def test_setup_logging_uses_env_var_overrides(tmpdir, dictConfigMock, monkeypatch):
    fake_settings = Settings(
        logging=LoggingSettings(settings_path=tmpdir.join("does-not-exist.yaml"))
    )
    expected_config = yaml.safe_load(DEFAULT_LOGGING_SETTINGS_PATH.read_text())

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
