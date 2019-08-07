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
    assert f.name not in storage
    res = storage.add_flow(f)
    assert res == "test"
    assert f.name in storage


def test_add_flow_raises_if_name_conflict():
    storage = Memory()
    f = Flow("test")
    res = storage.add_flow(f)
    g = Flow("test")
    with pytest.raises(ValueError, match='name "test"'):
        storage.add_flow(g)


def test_get_env_runner_raises():
    s = Memory()
    with pytest.raises(NotImplementedError):
        s.get_env_runner("")


def test_get_flow_raises_if_flow_not_present():
    s = Memory()
    with pytest.raises(ValueError):
        s.get_flow("test")


def test_get_flow_returns_flow():
    s = Memory()
    f = Flow("test")
    s.add_flow(f)
    runner = s.get_flow("test")
    assert runner is f


def test_containment():
    s = Memory()
    f = Flow("test")
    s.add_flow(f)

    assert True not in s
    assert f not in s
    assert "test" in s
    assert Flow("other") not in s
    assert "other" not in s


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

    assert "test" in s
    assert "other" in s
    assert "not" not in s

    assert s.get_flow("test") is f
    assert s.get_flow("other") is g

    assert s.flows["test"] is f
    assert s.flows["other"] is g
