import os
import tempfile

import cloudpickle
import pytest

import prefect
from prefect import Flow
from prefect.environments.storage import Local
from prefect.utilities.configuration import set_temporary_config


def test_create_local_storage():
    storage = Local()
    assert storage
    end_path = os.path.join(".prefect", "flows")
    assert storage.directory.endswith(end_path)


def test_create_local_storage_with_custom_dir():
    storage = Local(directory=".")
    assert storage
    assert os.path.isabs(storage.directory)


def test_create_local_storage_without_validation():
    storage = Local(directory="C:\\Users\\chris\\.prefect\\flows", validate=False)
    assert storage
    assert storage.directory == "C:\\Users\\chris\\.prefect\\flows"


def test_add_flow_to_storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = Local(directory=tmpdir)
        f = Flow("test")
        assert f.name not in storage

        res = storage.add_flow(f)
        assert res.endswith("test.prefect")
        assert f.name in storage

        with open(os.path.join(tmpdir, "test.prefect"), "rb") as f:
            wat = f.read()

    assert isinstance(wat, bytes)
    assert cloudpickle.loads(wat).name == "test"


def test_add_flow_raises_if_name_conflict():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = Local(directory=tmpdir)
        f = Flow("test")
        res = storage.add_flow(f)
        g = Flow("test")
        with pytest.raises(ValueError, match='name "test"'):
            storage.add_flow(g)


def test_get_env_runner_raises():
    s = Local()
    with pytest.raises(NotImplementedError):
        s.get_env_runner("")


def test_get_flow_raises_if_flow_not_present():
    s = Local()
    with pytest.raises(ValueError):
        s.get_flow("test")


def test_get_flow_returns_flow():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = Local(directory=tmpdir)
        f = Flow("test")
        loc = storage.add_flow(f)
        runner = storage.get_flow(loc)
        assert runner == f


def test_containment():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = Local(directory=tmpdir)
        f = Flow("test")
        s.add_flow(f)

        assert True not in s
        assert f not in s
        assert "test" in s
        assert Flow("other") not in s
        assert "other" not in s


def test_build_returns_self():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = Local(directory=tmpdir)
        assert s.build() is s

        f = Flow("test")
        s.add_flow(f)
        assert s.build() is s


def test_multiple_flows_in_storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = Local(directory=tmpdir)
        f = Flow("test")
        g = Flow("other")
        z = Flow("not")
        f_loc = s.add_flow(f)
        g_loc = s.add_flow(g)

        assert "test" in s
        assert "other" in s
        assert "not" not in s

        assert s.get_flow(f_loc) == f
        assert s.get_flow(g_loc) == g

        assert s.flows["test"] == f_loc
        assert s.flows["other"] == g_loc


def test_add_flow_with_weird_name_is_cleaned():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = Local(directory=tmpdir)
        flow = Flow("WELL what do you know?!~? looks like a test!!!!")
        loc = s.add_flow(flow)
        assert "?" not in loc
        assert "!" not in loc
        assert " " not in loc
        assert "~" not in loc
