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
    bad_value = "${general.bad_key}"

    [env_vars]
    interpolated_path = "$PATH"
    interpolated_from_non_string_key_bool = "${env_vars.true}"
    interpolated_from_non_string_key_string = "${env_vars.true} string"
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
    try:
        os.environ["PREFECT__ENV_VARS__NEW_KEY"] = "TEST"
        os.environ["PREFECT__ENV_VARS__TRUE"] = "true"
        os.environ["PREFECT__ENV_VARS__FALSE"] = "false"
        os.environ["PREFECT__ENV_VARS__INT"] = "10"
        os.environ["PREFECT__ENV_VARS__NEGATIVE_INT"] = "-10"
        os.environ["PREFECT__ENV_VARS__FLOAT"] = "7.5"
        os.environ["PREFECT__ENV_VARS__NEGATIVE_FLOAT"] = "-7.5"
        yield configuration.load_config_file(
            path=test_config_file_path, env_var_prefix="PREFECT"
        )
    finally:
        del os.environ["PREFECT__ENV_VARS__NEW_KEY"]
        del os.environ["PREFECT__ENV_VARS__TRUE"]
        del os.environ["PREFECT__ENV_VARS__FALSE"]
        del os.environ["PREFECT__ENV_VARS__INT"]
        del os.environ["PREFECT__ENV_VARS__NEGATIVE_INT"]
        del os.environ["PREFECT__ENV_VARS__FLOAT"]
        del os.environ["PREFECT__ENV_VARS__NEGATIVE_FLOAT"]


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


def test_env_var_interpolation(config):
    assert config.env_vars.interpolated_path == os.getenv("PATH")


def test_string_to_type_function():

    assert configuration.string_to_type("true") is True
    assert configuration.string_to_type("True") is True
    assert configuration.string_to_type("false") is False
    assert configuration.string_to_type("False") is False

    assert configuration.string_to_type("1") is 1
    assert configuration.string_to_type("1.5") == 1.5

    assert configuration.string_to_type("-1") == -1
    assert configuration.string_to_type("-1.5") == -1.5

    assert configuration.string_to_type("x") == "x"


def test_env_var_interpolation_with_type_assignment(config):
    assert config.env_vars.true is True
    assert config.env_vars.false is False
    assert config.env_vars.int is 10
    assert config.env_vars.negative_int == -10
    assert config.env_vars.float == 7.5
    assert config.env_vars.negative_float == -7.5


def test_env_var_interpolation_with_type_interpolation(config):
    assert config.env_vars.interpolated_from_non_string_key_bool is True
    assert config.env_vars.interpolated_from_non_string_key_string == "True string"


def test_env_var_interpolation_doesnt_match_internal_dollar_sign(config):
    assert config.env_vars.not_interpolated_path == "xxx$PATHxxx"


def test_env_var_interpolation_with_nonexistant_key(config):
    assert config.interpolation.bad_value == ""


def test_env_var_overrides_new_key(config):
    assert config.env_vars.new_key == "TEST"


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
