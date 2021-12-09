from prefect.flow_runners import FlowRunner, SubprocessFlowRunner
import pytest
import pydantic


def test_base_flow_runner_is_universal():
    assert FlowRunner().typename == "universal"


def test_flow_runner_env_config():
    assert FlowRunner(env={"foo": "bar"}).env == {"foo": "bar"}


def test_flow_runner_env_config_casts_to_strings():
    assert FlowRunner(env={"foo": 1}).env == {"foo": "1"}


def test_flow_runner_env_config_errors_if_not_castable():
    with pytest.raises(pydantic.ValidationError):
        FlowRunner(env={"foo": object()})
