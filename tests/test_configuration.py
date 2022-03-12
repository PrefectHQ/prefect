import datetime
import os
import sys
import tempfile

import pytest

import prefect
from prefect import configuration
from prefect.configuration import Config, to_environment_variables
from prefect.utilities.collections import dict_to_flatdict

template = b"""
    debug = false

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

    [secrets]
    password = "1234"
    very_private = "000"
    """


@pytest.fixture
def test_config_file_path():
    with tempfile.TemporaryDirectory() as test_config_dir:
        test_config_loc = os.path.join(test_config_dir, "test_config.toml")
        with open(test_config_loc, "wb") as test_config:
            test_config.write(template)
        yield test_config_loc


@pytest.fixture
def config(test_config_file_path, monkeypatch):

    monkeypatch.setenv("PREFECT_TEST__ENV_VARS__NEW_KEY", "TEST")
    monkeypatch.setenv("PREFECT_TEST__ENV_VARS__TWICE__NESTED__NEW_KEY", "TEST")
    monkeypatch.setenv("PREFECT_TEST__ENV_VARS__TRUE", "true")
    monkeypatch.setenv("PREFECT_TEST__ENV_VARS__FALSE", "false")
    monkeypatch.setenv("PREFECT_TEST__ENV_VARS__INT", "10")
    monkeypatch.setenv("PREFECT_TEST__ENV_VARS__NEGATIVE_INT", "-10")
    monkeypatch.setenv("PREFECT_TEST__ENV_VARS__FLOAT", "7.5")
    monkeypatch.setenv("PREFECT_TEST__ENV_VARS__NEGATIVE_FLOAT", "-7.5")
    monkeypatch.setenv(
        "PREFECT_TEST__CONTEXT__SECRETS__AWS_CREDENTIALS",
        '{"ACCESS_KEY": "abcdef", "SECRET_ACCESS_KEY": "ghijklmn"}',
    )
    monkeypatch.setenv("PATH", "1/2/3")
    monkeypatch.setenv(
        "PREFECT_TEST__ENV_VARS__ESCAPED_CHARACTERS", "line 1\nline 2\rand 3\tand 4"
    )

    yield configuration.load_configuration(
        test_config_file_path, env_var_prefix="PREFECT_TEST"
    )


def test_keys(config):
    assert "debug" in config
    assert "general" in config
    assert "nested" in config.general
    assert "x" not in config


def test_dicts_are_created(config):
    val = config.context.secrets.AWS_CREDENTIALS
    assert isinstance(val, dict)
    assert val["ACCESS_KEY"] == "abcdef"


def test_getattr_missing(config):
    with pytest.raises(AttributeError, match="object has no attribute"):
        config.hello


def test_debug(config):
    assert config.debug is False


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
    assert config.env_vars.interpolated_path == os.environ.get("PATH")


def test_to_environment_variables(config):
    env = to_environment_variables(
        config, include={"general.x", "general.y", "general.nested.x", "debug"}
    )
    assert env == {
        "PREFECT__GENERAL__Y": "hi",
        # Converts values to strings
        "PREFECT__GENERAL__X": "1",
        "PREFECT__DEBUG": "False",
        # Handles nesting
        "PREFECT__GENERAL__NESTED__X": "1",
    }


def test_to_environment_variables_respects_prefix():
    env = to_environment_variables(
        Config({"key": "value"}), include={"key"}, prefix="FOO"
    )
    assert env == {"FOO__KEY": "value"}


def test_to_environment_variables_roundtrip(config, monkeypatch, test_config_file_path):
    keys = [".".join(k) for k in dict_to_flatdict(config)]

    # Note prefix is different to avoid colliding with the `config` fixture env
    env = to_environment_variables(config, include=keys, prefix="PREFECT_TEST_ROUND")

    for k, v in env.items():
        monkeypatch.setenv(k, v)

    new_config = configuration.load_configuration(
        test_config_file_path, env_var_prefix="PREFECT_TEST_ROUND"
    )
    assert new_config == config


def test_string_to_type_function():

    assert configuration.string_to_type("true") is True
    assert configuration.string_to_type("True") is True
    assert configuration.string_to_type("TRUE") is True
    assert configuration.string_to_type("trUe") is True
    assert configuration.string_to_type("false") is False
    assert configuration.string_to_type("False") is False
    assert configuration.string_to_type("FALSE") is False
    assert configuration.string_to_type("falSe") is False

    assert configuration.string_to_type("1") == 1
    assert configuration.string_to_type("1.5") == 1.5

    assert configuration.string_to_type("-1") == -1
    assert configuration.string_to_type("-1.5") == -1.5

    assert configuration.string_to_type("x") == "x"


def test_env_var_interpolation_with_type_assignment(config):
    assert config.env_vars.true is True
    assert config.env_vars.false is False
    assert config.env_vars.int == 10
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


def test_env_var_creates_nested_keys(config):
    assert config.env_vars.twice.nested.new_key == "TEST"


def test_env_var_escaped(config):
    assert config.env_vars.escaped_characters == "line 1\nline 2\rand 3\tand 4"


def test_copy_leaves_values_mutable(config):

    config = Config(config, default_box=True)
    config.x.y.z = [1]
    new = config.copy()
    assert new.x.y.z == [1]
    new.x.y.z.append(2)
    assert config.x.y.z == [1, 2]


def test_copy_doesnt_make_keys_mutable(config):

    new = config.copy()
    new.general.z = 1
    assert "z" not in config.general


class TestUserConfig:
    def test_load_user_config(self, test_config_file_path):

        with tempfile.TemporaryDirectory() as user_config_dir:
            user_config_loc = os.path.join(user_config_dir, "test_config.toml")
            with open(user_config_loc, "wb") as user_config:
                user_config.write(
                    b"""
                    [general]
                    x = 2

                    [user]
                    foo = "bar"
                    """
                )
            config = configuration.load_configuration(
                path=test_config_file_path, user_config_path=user_config_loc
            )

            # check that user values are loaded
            assert config.general.x == 2
            assert config.user.foo == "bar"

            # check that default values are preserved
            assert config.general.y == "hi"

            # check that interpolation takes place after user config is loaded
            assert config.general.nested.x == 2


class TestProcessTaskDefaults:
    def test_process_task_defaults_called_on_prefect_config(self):
        "If task defaults was called, the max_retry default should be 0 instead of False"
        assert prefect.config.tasks.defaults.max_retries == 0

    def test_max_retries_is_0_if_not_set(self):
        config = configuration.process_task_defaults(Config())
        assert config.tasks.defaults.max_retries == 0

    def test_max_retries_is_0_if_false(self):
        config = Config(default_box=True)
        config.tasks.defaults.max_retries = False
        config = configuration.process_task_defaults(config)
        assert config.tasks.defaults.max_retries == 0

    def test_max_retries_is_0_if_none(self):
        config = Config(default_box=True)
        config.tasks.defaults.max_retries = None
        config = configuration.process_task_defaults(config)
        assert config.tasks.defaults.max_retries == 0

    def test_max_retries_is_0_if_0(self):
        config = Config(default_box=True)
        config.tasks.defaults.max_retries = 0
        config = configuration.process_task_defaults(config)
        assert config.tasks.defaults.max_retries == 0

    def test_max_retries_ignored_if_set(self):
        config = Config(default_box=True)
        config.tasks.defaults.max_retries = 3
        config = configuration.process_task_defaults(config)
        assert config.tasks.defaults.max_retries == 3

    def test_retry_delay_is_none_if_not_set(self):
        config = configuration.process_task_defaults(Config())
        assert config.tasks.defaults.retry_delay is None

    def test_retry_delay_is_none_if_false(self):
        config = Config(default_box=True)
        config.tasks.defaults.retry_delay = False
        config = configuration.process_task_defaults(config)
        assert config.tasks.defaults.retry_delay is None

    def test_retry_delay_is_none_if_none(self):
        config = Config(default_box=True)
        config.tasks.defaults.retry_delay = None
        config = configuration.process_task_defaults(config)
        assert config.tasks.defaults.retry_delay is None

    def test_retry_delay_is_timedelta_if_int(self):
        config = Config(default_box=True)
        config.tasks.defaults.retry_delay = 5
        config = configuration.process_task_defaults(config)
        assert config.tasks.defaults.retry_delay == datetime.timedelta(seconds=5)

    def test_retry_delay_is_timedelta_if_timedelta(self):
        config = Config(default_box=True)
        config.tasks.defaults.retry_delay = datetime.timedelta(seconds=5)
        config = configuration.process_task_defaults(config)
        assert config.tasks.defaults.retry_delay == datetime.timedelta(seconds=5)

    def test_timeout_is_none_if_not_set(self):
        config = configuration.process_task_defaults(Config())
        assert config.tasks.defaults.timeout is None

    def test_timeout_is_none_if_false(self):
        config = Config(default_box=True)
        config.tasks.defaults.timeout = False
        config = configuration.process_task_defaults(config)
        assert config.tasks.defaults.timeout is None

    def test_timeout_is_none_if_none(self):
        config = Config(default_box=True)
        config.tasks.defaults.timeout = None
        config = configuration.process_task_defaults(config)
        assert config.tasks.defaults.timeout is None

    def test_timeout_is_timedelta_if_timedelta(self):
        config = Config(default_box=True)
        config.tasks.defaults.timeout = datetime.timedelta(seconds=5)
        config = configuration.process_task_defaults(config)
        assert config.tasks.defaults.timeout == datetime.timedelta(seconds=5)


class TestConfigValidation:
    def test_invalid_keys_raise_error(self):

        with tempfile.TemporaryDirectory() as test_config_dir:
            test_config_loc = os.path.join(test_config_dir, "test_config.toml")
            with open(test_config_loc, "wb") as test_config:
                test_config.write(
                    b"""
                    [outer]
                    x = 1

                        [outer.keys]
                        a = "b"
                    """
                )

            with pytest.raises(ValueError):
                configuration.load_configuration(test_config_loc)

    def test_invalid_env_var_raises_error(self, monkeypatch):
        monkeypatch.setenv("PREFECT_TEST__X__Y__KEYS__Z", "TEST")

        with tempfile.TemporaryDirectory() as test_config_dir:
            test_config_loc = os.path.join(test_config_dir, "test_config.toml")
            with open(test_config_loc, "wb") as test_config:
                test_config.write(b"")
            with pytest.raises(ValueError):
                configuration.load_configuration(
                    test_config_loc, env_var_prefix="PREFECT_TEST"
                )

    def test_mixed_case_keys_are_ok(self):
        with tempfile.TemporaryDirectory() as test_config_dir:
            test_config_loc = os.path.join(test_config_dir, "test_config.toml")
            with open(test_config_loc, "wb") as test_config:
                test_config.write(
                    b"""
                    [SeCtIoN]
                    KeY = 1
                    """
                )

            config = configuration.load_configuration(test_config_loc)

        assert "KeY" in config.SeCtIoN
        assert config.SeCtIoN.KeY == 1

    def test_env_vars_are_interpolated_as_lower_case(self, monkeypatch):

        monkeypatch.setenv("PREFECT_TEST__SECTION__KEY", "2")

        with tempfile.TemporaryDirectory() as test_config_dir:
            test_config_loc = os.path.join(test_config_dir, "test_config.toml")
            with open(test_config_loc, "wb") as test_config:
                test_config.write(
                    b"""
                    [SeCtIoN]
                    KeY = 1
                    """
                )

            config = configuration.load_configuration(
                test_config_loc, env_var_prefix="PREFECT_TEST"
            )

        assert "KeY" in config.SeCtIoN
        assert config.SeCtIoN.KeY == 1
        assert config.section.key == 2

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows converts env vars to uppercase automatically.",
    )
    def test_env_vars_for_secrets_alone_are_not_lower_cased(self, monkeypatch):

        monkeypatch.setenv("PREFECT_TEST__CONTEXT__SECRETS__mY_spECIal_kEY", "42")
        monkeypatch.setenv("PREFECT_TEST__CONTEXT__strange_VAlUE", "false")
        monkeypatch.setenv("PREFECT_TEST__CONTEXT__FLOW_RUN_ID", "12345")
        monkeypatch.setenv("PREFECT_TEST__CONTEXT__FLOW_ID", "56789")

        with tempfile.TemporaryDirectory() as test_config_dir:
            test_config_loc = os.path.join(test_config_dir, "test_config.toml")
            with open(test_config_loc, "wb") as test_config:
                test_config.write(
                    b"""
                    [context]
                    spECIAL_TOP_key = "foo"

                    [context.secrets]
                    KeY = 1
                    """
                )

            config = configuration.load_configuration(
                test_config_loc, env_var_prefix="PREFECT_TEST"
            )

        assert "secrets" in config.context
        assert config.context.secrets.mY_spECIal_kEY == 42
        assert config.context.secrets.KeY == 1
        assert config.context.spECIAL_TOP_key == "foo"
        assert config.context.flow_run_id == 12345
        assert config.context.flow_id == 56789
        assert config.context.strange_value is False
