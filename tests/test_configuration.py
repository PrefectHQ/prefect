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

    """


@pytest.fixture
def config():
    with tempfile.NamedTemporaryFile() as default_config:
        default_config.write(template)
        default_config.seek(0)
        return configuration.load_config_file(path=default_config.name)

def test_keys(config):
    assert 'general' in config
    assert 'nested' in config.general
    assert 'x' not in config

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
    assert config.env_vars.not_interpolated_path == 'xxx$PATHxxx'


def test_env_var_overrides():
    os.environ["PREFECT__ENV_VARS__TEST"] = "OVERRIDE!"
    assert config().env_vars.test == "OVERRIDE!"
