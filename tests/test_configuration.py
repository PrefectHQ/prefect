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
    try:
        ev = "PREFECT__ENV_VARS__TEST"
        os.environ[ev] = "OVERRIDE!"
        config = configuration.load_config_file(
            test_config_file_path, env_var_prefix="PREFECT"
        )
        assert config.env_vars.test == "OVERRIDE!"
    finally:
        del os.environ[ev]


def test_merge_configurations(test_config_file_path):

    default_config = configuration.config

    assert default_config.logging.format != "log-format"
    assert default_config.flows.default_version == "1"

    config = configuration.load_configuration(
        config_path=test_config_file_path, merge_into_config=default_config
    )

    assert config.logging.format == "log-format"
    assert config.flows.default_version == "1"
    assert config.interpolation.value == 1


def test_load_user_config(test_config_file_path):

    with tempfile.NamedTemporaryFile() as user_config:
        user_config.write(
            b"""
            [general]
            x = 2

            [user]
            foo = "bar"
            """
        )
        user_config.seek(0)

        test_config = configuration.load_configuration(test_config_file_path)
        config = configuration.load_configuration(
            user_config.name, merge_into_config=test_config
        )
        assert config.general.x == 2
        assert config.user.foo == "bar"
