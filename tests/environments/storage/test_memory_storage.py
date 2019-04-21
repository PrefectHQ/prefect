import pytest

import prefect
from prefect import Flow
from prefect.engine.cloud import CloudFlowRunner
from prefect.engine.flow_runner import FlowRunner
from prefect.environments.storage import Memory
from prefect.utilities.configuration import set_temporary_config


def test_create_memory_storage():
    storage = Memory()
    assert storage


def test_add_flow_to_storage():
    storage = Memory()
    f = Flow("test")
    res = storage.add_flow(f)
    assert res == "test"
    assert f in storage


def test_add_flow_raises_if_name_conflict():
    storage = Memory()
    f = Flow("test")
    res = storage.add_flow(f)
    g = Flow("test")
    with pytest.raises(ValueError) as exc:
        storage.add_flow(g)
    assert 'name "test"' in str(exc.value)


def test_get_flow_location_raises_if_not_present():
    s = Memory()
    f = Flow("test")
    with pytest.raises(ValueError):
        s.get_flow_location("test")

    s.add_flow(f)
    res = s.get_flow_location("test")
    assert res == "test"


def test_get_env_runner_raises():
    s = Memory()
    with pytest.raises(NotImplementedError):
        s.get_env_runner("")


def test_get_runner_raises_if_flow_not_present():
    s = Memory()
    with pytest.raises(ValueError):
        s.get_runner("test")


def test_get_runner_returns_flow_or_flow_runner():
    s = Memory()
    f = Flow("test")
    s.add_flow(f)
    runner = s.get_runner("test")
    assert runner is f

    with set_temporary_config({"engine.flow_runner.default_class": FlowRunner}):
        runner = s.get_runner("test", return_flow=False)
        assert isinstance(runner, FlowRunner)
        assert runner.flow is f


def test_get_runner_returns_flow_or_flow_runner_responds_to_config():
    s = Memory()
    f = Flow("test")
    s.add_flow(f)

    with set_temporary_config({"engine.flow_runner.default_class": CloudFlowRunner}):
        runner = s.get_runner("test", return_flow=False)
        assert isinstance(runner, CloudFlowRunner)
        assert runner.flow is f


def test_containment():
    s = Memory()
    f = Flow("test")
    s.add_flow(f)

    assert True not in s
    assert "test" not in s
    assert f in s
    assert Flow("other") not in s


def test_build_returns_self():
    s = Memory()
    assert s.build() is s

    f = Flow("test")
    s.add_flow(f)
    assert s.build() is s


def test_multiple_flows_in_storage():
    s = Memory()
    f = Flow("test")
    g = Flow("other")
    z = Flow("not")
    s.add_flow(f)
    s.add_flow(g)

    assert f in s
    assert g in s
    assert z not in s

    assert s.get_runner("test") is f
    assert s.get_runner("other") is g

    assert s.get_flow_location("test") == "test"
    assert s.get_flow_location("other") == "other"
