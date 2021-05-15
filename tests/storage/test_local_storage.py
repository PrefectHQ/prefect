import os
import socket
import textwrap

import pytest

from prefect import Flow
from prefect.engine.results import LocalResult
from prefect.storage import Local


def test_create_local_storage():
    storage = Local(secrets=["AUTH"])
    assert storage
    end_path = os.path.join(".prefect", "flows")
    assert storage.directory.endswith(end_path)
    assert isinstance(storage.result, LocalResult)

    end_path = os.path.join(".prefect", "results")
    assert storage.result.dir.endswith(end_path)
    assert storage.secrets == ["AUTH"]


def test_create_local_storage_with_custom_dir():
    storage = Local(directory=".")
    assert storage
    assert os.path.isabs(storage.directory)
    assert isinstance(storage.result, LocalResult)
    assert storage.result.dir == storage.directory


def test_create_local_storage_without_validation():
    storage = Local(directory="C:\\Users\\chris\\.prefect\\flows", validate=False)
    assert storage
    assert storage.directory == "C:\\Users\\chris\\.prefect\\flows"

    assert isinstance(storage.result, LocalResult)
    assert storage.result.dir == storage.directory


def test_add_flow_to_storage(tmpdir):
    storage = Local(directory=str(tmpdir))
    f = Flow("test")
    assert f.name not in storage

    res = storage.add_flow(f)

    flow_dir = os.path.join(tmpdir, "test")
    assert os.path.exists(flow_dir)
    assert len(os.listdir(flow_dir)) == 1
    assert res.startswith(flow_dir)

    assert f.name in storage

    f2 = storage.get_flow(f.name)
    assert f2.name == "test"


def test_add_flow_file_to_storage(tmpdir):
    contents = """from prefect import Flow\nf=Flow('test-flow')"""

    full_path = os.path.join(tmpdir, "flow.py")

    with open(full_path, "w") as f:
        f.write(contents)

    f = Flow("test-flow")
    storage = Local(stored_as_script=True)

    with pytest.raises(ValueError):
        storage.add_flow(f)

    storage = Local(stored_as_script=True, path=full_path)

    loc = storage.add_flow(f)
    assert loc == full_path
    assert f.name in storage


def test_add_flow_raises_if_name_conflict(tmpdir):
    storage = Local(directory=str(tmpdir))
    f = Flow("test")
    storage.add_flow(f)
    g = Flow("test")
    with pytest.raises(ValueError, match='name "test"'):
        storage.add_flow(g)


def test_get_flow_raises_if_flow_not_present():
    s = Local()
    with pytest.raises(ValueError):
        s.get_flow("test")


def test_get_flow_returns_flow(tmpdir):
    storage = Local(directory=str(tmpdir))
    f = Flow("test")
    storage.add_flow(f)
    f2 = storage.get_flow(f.name)
    assert f2 == f


def test_get_flow_from_file_returns_flow(tmpdir):
    contents = textwrap.dedent(
        """
        from prefect import Flow
        f1 = Flow('flow-1')
        f2 = Flow('flow-2')
        """
    )

    full_path = os.path.join(tmpdir, "flow.py")

    with open(full_path, "w") as f:
        f.write(contents)

    f1 = Flow("flow-1")
    f2 = Flow("flow-2")
    storage = Local(stored_as_script=True, path=full_path)
    storage.add_flow(f1)
    storage.add_flow(f2)

    f1_2 = storage.get_flow(f1.name)
    f2_2 = storage.get_flow(f2.name)
    assert f1_2.name == f1.name
    assert f2_2.name == f2.name
    f1_2.run()
    f2_2.run()


def test_containment(tmpdir):
    s = Local(directory=str(tmpdir))
    f = Flow("test")
    s.add_flow(f)

    assert True not in s
    assert f not in s
    assert "test" in s
    assert Flow("other") not in s
    assert "other" not in s


def test_build_returns_self(tmpdir):
    s = Local(directory=str(tmpdir))
    assert s.build() is s

    f = Flow("test")
    s.add_flow(f)
    assert s.build() is s


def test_multiple_flows_in_storage(tmpdir):
    s = Local(directory=str(tmpdir))
    f = Flow("test")
    g = Flow("other")
    f_loc = s.add_flow(f)
    g_loc = s.add_flow(g)

    assert "test" in s
    assert "other" in s
    assert "not" not in s

    assert s.get_flow(f.name) == f
    assert s.get_flow(g.name) == g

    assert s.flows["test"] == f_loc
    assert s.flows["other"] == g_loc


def test_add_flow_with_weird_name_is_cleaned(tmpdir):
    s = Local(directory=str(tmpdir))
    flow = Flow("WELL what do you know?!~? looks like a test!!!!")
    loc = s.add_flow(flow)
    assert "?" not in loc
    assert "!" not in loc
    assert " " not in loc
    assert "~" not in loc


def test_build_healthchecks(tmpdir):
    s = Local(directory=str(tmpdir))
    flow = Flow("TestFlow")
    s.add_flow(flow)
    assert s.build()


def test_build_healthcheck_returns_on_no_flows(tmpdir):
    s = Local(directory=str(tmpdir))
    assert s.build()


def test_labels_includes_hostname(tmpdir):
    s = Local(directory=str(tmpdir))
    assert socket.gethostname() in s.labels


def test_opt_out_of_hostname_label(tmpdir):
    s = Local(directory=str(tmpdir), add_default_labels=False)
    assert socket.gethostname() not in s.labels
