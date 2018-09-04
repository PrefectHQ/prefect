import os
import tempfile
import uuid

import pytest

from prefect import configuration

template = b"""
    [general]
    x = 1
    y = "hi"

        [general.nested]
        x = "${general.x}"
        x_interpolated = "${general.x} + 1"
        y = "${general.y} or bye"

    [interpolation]
    key = "x"
    value = "${general.nested.${interpolation.key}}"

    [env_vars]
    interpolated_path = "$PATH"
    not_interpolated_path = "xxx$PATHxxx"

    [logging]
    format = "log-format"

    """


@pytest.fixture
def test_config_file_path():
    with tempfile.NamedTemporaryFile() as test_config:
        test_config.write(template)
        test_config.seek(0)
        yield test_config.name


@pytest.fixture
def config(test_config_file_path):
    return configuration.load_config_file(path=test_config_file_path)


def test_keys(config):
    assert "general" in config
    assert "nested" in config.general
    assert "x" not in config


def test_repr(config):
    assert repr(config) == "<Config: 'env_vars', 'general', 'interpolation', 'logging'>"
    assert repr(config.general) == "<Config: 'nested', 'x', 'y'>"


def test_general(config):
    assert config.general.x == 1
    assert config.general.y == "hi"


def test_general_nested(config):
    assert config.general.nested.x == config.general.x == 1
    assert config.general.nested.x_interpolated == "1 + 1"
    assert config.general.nested.y == "hi or bye"


def test_interpolation(config):
    assert config.interpolation.value == config.general.nested.x == 1


def test_env_var_expansion(config):
    assert config.env_vars.interpolated_path == os.getenv("PATH")


def test_env_var_interpolation(config):
    assert config.env_vars.not_interpolated_path == "xxx$PATHxxx"


def test_env_var_overrides(test_config_file_path):
    os.environ["PREFECT__ENV_VARS__TEST"] = "OVERRIDE!"
    assert config(test_config_file_path).env_vars.test == "OVERRIDE!"


def test_load_user_config_and_update_default(test_config_file_path):
    config = configuration.load_configuration(
        default_config_path=configuration.DEFAULT_CONFIG,
        user_config_path=test_config_file_path,
    )
    assert "logging" in config

    # this comes from default
    assert config.logging.level == "INFO"
    # this comes from user
    assert config.logging.format == "log-format"

    # this comes from user
    assert "general" in config
    assert config.general.nested.x == 1
