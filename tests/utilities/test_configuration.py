import os
import tempfile
from datetime import timedelta

import pytest

import prefect
from prefect.core import Task
from prefect.utilities.configuration import set_temporary_config, set_permanent_user_config
from prefect import configuration


def test_set_temporary_config_is_temporary():
    # without this setting, the tasks will error because they have max_retries but no
    # retry delay
    with set_temporary_config({"tasks.defaults.retry_delay": timedelta(seconds=1)}):
        with set_temporary_config({"tasks.defaults.max_retries": 5}):
            with set_temporary_config({"tasks.defaults.max_retries": 1}):
                t1 = Task()
                assert t1.max_retries == 1
            t2 = Task()
            assert t2.max_retries == 5
    t3 = Task()
    assert t3.max_retries == 0


def test_set_temporary_config_can_invent_new_settings():
    with set_temporary_config({"flows.nested.nested_again.val": "5"}):
        assert prefect.config.flows.nested.nested_again.val == "5"

    with pytest.raises(AttributeError):
        assert prefect.config.flows.nested.nested_again.val == "5"


def test_set_temporary_config_with_multiple_keys():
    with set_temporary_config({"x.y.z": 1, "a.b.c": 2}):
        assert prefect.config.x.y.z == 1
        assert prefect.config.a.b.c == 2


def test_set_permanent_config():
    with tempfile.TemporaryDirectory() as test_config_dir:
        test_config_loc = os.path.join(test_config_dir, "test_config.toml")
        with open(test_config_loc, "wb") as test_config:
            test_config.write(
                b"""
                [server]
                host = "localhost"
                """
            )

        config = configuration.load_configuration(
            test_config_loc, env_var_prefix="PREFECT_TEST"
        )

        assert config.server.host == "localhost"

        fp = set_permanent_user_config({'server': {'host': 'another-server'}}, test_config_loc)

        config = configuration.load_configuration(
            test_config_loc, env_var_prefix="PREFECT_TEST"
        )
        assert config.server.host == "another-server"
        assert fp == test_config_loc
