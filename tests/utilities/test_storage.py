import os
import sys
import types
import textwrap

import pytest
import cloudpickle

import prefect
from prefect import Flow, Task
from prefect.environments import LocalEnvironment
from prefect.storage import Docker, Local
from prefect.exceptions import FlowStorageError
from prefect.utilities.storage import (
    get_flow_image,
    extract_flow_from_file,
    extract_flow_from_module,
    flow_to_bytes_pickle,
    flow_from_bytes_pickle,
)


def test_get_flow_image_docker_storage():
    flow = Flow(
        "test",
        environment=LocalEnvironment(),
        storage=Docker(registry_url="test", image_name="name", image_tag="tag"),
    )
    image = get_flow_image(flow=flow)
    assert image == "test/name:tag"


def test_get_flow_image_env_metadata():
    flow = Flow(
        "test",
        environment=LocalEnvironment(metadata={"image": "repo/name:tag"}),
        storage=Local(),
    )
    image = get_flow_image(flow=flow)
    assert image == "repo/name:tag"


def test_get_flow_image_raises_on_missing_info():
    flow = Flow(
        "test",
        environment=LocalEnvironment(),
        storage=Local(),
    )
    with pytest.raises(ValueError):
        get_flow_image(flow=flow)


class TestExtractFlowFromFile:
    @pytest.fixture
    def flow_path(self, tmpdir):
        contents = """from prefect import Flow\nf=Flow('flow-1')\nf2=Flow('flow-2')"""

        full_path = os.path.join(tmpdir, "flow.py")

        with open(full_path, "w") as f:
            f.write(contents)

        return full_path

    @pytest.fixture
    def flow_path_with_additional_file(self, tmpdir):
        contents = """\
        from prefect import Flow
        from pathlib import Path

        with open(str(Path(__file__).resolve().parent)+"/test.txt", "r") as f:
            name = f.read()
        
        f2 = Flow(name)
        """

        full_path = os.path.join(tmpdir, "flow.py")

        with open(full_path, "w") as f:
            f.write(textwrap.dedent(contents))

        with open(os.path.join(tmpdir, "test.txt"), "w") as f:
            f.write("test-flow")

        return full_path

    def test_extract_flow_from_file_path(self, flow_path):
        flow = extract_flow_from_file(file_path=flow_path)
        assert flow.name == "flow-1"
        assert flow.run().is_successful()

        flow = extract_flow_from_file(file_path=flow_path, flow_name="flow-1")
        assert flow.name == "flow-1"

        flow = extract_flow_from_file(file_path=flow_path, flow_name="flow-2")
        assert flow.name == "flow-2"

    def test_extract_flow_from_file_path_can_load_files_from_same_directory(
        self, flow_path_with_additional_file
    ):
        flow = extract_flow_from_file(file_path=flow_path_with_additional_file)
        assert flow.name == "test-flow"
        assert flow.run().is_successful()

    def test_extract_flow_from_file_contents(self, flow_path):
        with open(flow_path, "r") as f:
            contents = f.read()

        flow = extract_flow_from_file(file_contents=contents)
        assert flow.name == "flow-1"
        assert flow.run().is_successful()

        flow = extract_flow_from_file(file_contents=contents, flow_name="flow-1")
        assert flow.name == "flow-1"

        flow = extract_flow_from_file(file_contents=contents, flow_name="flow-2")
        assert flow.name == "flow-2"

    def test_extract_flow_from_file_errors(self, flow_path):
        with pytest.raises(ValueError, match="but not both"):
            extract_flow_from_file(file_path="", file_contents="")

        with pytest.raises(ValueError, match="Provide either"):
            extract_flow_from_file()

        expected = (
            "Flow 'not-real' not found in file. Found flows:\n- 'flow-1'\n- 'flow-2'"
        )
        with pytest.raises(ValueError, match=expected):
            extract_flow_from_file(file_path=flow_path, flow_name="not-real")

        with pytest.raises(ValueError, match="No flows found in file."):
            extract_flow_from_file(file_contents="")

    @pytest.mark.parametrize("method", ["run", "register"])
    def test_extract_flow_from_file_raises_on_run_register(self, tmpdir, method):
        contents = f"from prefect import Flow\nf=Flow('test-flow')\nf.{method}()"

        full_path = os.path.join(tmpdir, "flow.py")

        with open(full_path, "w") as f:
            f.write(contents)

        with prefect.context({"loading_flow": True}):
            with pytest.warns(Warning):
                extract_flow_from_file(file_path=full_path)


@pytest.fixture
def mymodule(monkeypatch):
    mod_name = "mymodule"
    module = types.ModuleType(mod_name)
    monkeypatch.setitem(sys.modules, mod_name, module)
    return module


def test_extract_flow_from_module(mymodule):
    class Obj:
        flow = Flow("multi-level flow")

    mymodule.flow = Flow("top level flow")
    mymodule.multi_level = Obj()
    mymodule.bad_type = 1

    # module with single top-level flow has flow auto-inferred
    assert extract_flow_from_module("mymodule") is mymodule.flow
    # Specifying name/attribute still works
    assert extract_flow_from_module("mymodule", "top level flow") is mymodule.flow
    assert extract_flow_from_module("mymodule:flow", "top level flow") is mymodule.flow

    # Multi-level attrs work
    assert extract_flow_from_module("mymodule:multi_level.flow") is Obj.flow

    # Multiple top-level flows
    mymodule.flow2 = Flow("a second flow")
    assert extract_flow_from_module("mymodule", "top level flow") is mymodule.flow
    assert extract_flow_from_module("mymodule", "a second flow") is mymodule.flow2

    # Multiple flows not auto-inferred
    with pytest.raises(ValueError, match="Multiple flows found"):
        extract_flow_from_module("mymodule")

    # Name not found
    with pytest.raises(ValueError, match="Failed to find flow"):
        extract_flow_from_module("mymodule", "unknown name")

    # Name doesn't match specified object
    with pytest.raises(ValueError, match="Flow at 'mymodule:flow' is named"):
        extract_flow_from_module("mymodule:flow", "incorrect name")

    # Not a flow object
    with pytest.raises(TypeError, match="Object at 'mymodule:bad_type'"):
        extract_flow_from_module("mymodule:bad_type")


def test_extract_flow_from_module_callable_objects(mymodule):
    flow1 = Flow("flow 1")
    flow2 = Flow("flow 2")

    class Obj:
        def build_flow(self):
            return flow2

    mymodule.build_flow = lambda: flow1
    mymodule.multi_level = Obj()
    mymodule.bad_type = lambda: 1

    assert extract_flow_from_module("mymodule:build_flow") is flow1
    assert extract_flow_from_module("mymodule:build_flow", "flow 1") is flow1
    assert extract_flow_from_module("mymodule:multi_level.build_flow") is flow2

    with pytest.raises(TypeError, match="Object at 'mymodule:bad_type'"):
        extract_flow_from_module("mymodule:bad_type")


class RaiseOnLoad(Task):
    def __init__(self, exc):
        super().__init__()
        self.exc = exc

    @staticmethod
    def _raise(exc):
        raise exc

    def __reduce__(self):
        return (self._raise, (self.exc,))


class TestFlowToFromBytesPickle:
    def test_serialize_deserialize(self):
        s = flow_to_bytes_pickle(Flow("test"))
        assert isinstance(s, bytes)
        flow = flow_from_bytes_pickle(s)
        assert isinstance(flow, Flow)
        assert flow.name == "test"

    def test_flow_from_bytes_loads_raw_pickle(self):
        """Older versions of prefect serialized flows as straight pickle bytes.
        This checks that we can still deserialize these payloads"""
        s = cloudpickle.dumps(Flow("test"))
        flow = flow_from_bytes_pickle(s)
        assert isinstance(flow, Flow)
        assert flow.name == "test"

    def test_flow_from_bytes_warns_prefect_version_mismatch(self, monkeypatch):
        s = flow_to_bytes_pickle(Flow("test"))
        monkeypatch.setattr(prefect, "__version__", "0.1.0")
        with pytest.warns(UserWarning, match="This flow was built using Prefect"):
            flow = flow_from_bytes_pickle(s)
        assert isinstance(flow, Flow)
        assert flow.name == "test"

    @pytest.mark.parametrize("version_mismatch", [False, True])
    @pytest.mark.parametrize("import_error", [False, True])
    def test_flow_from_bytes_error(self, monkeypatch, version_mismatch, import_error):
        exc = ImportError("mymodule") if import_error else ValueError("Oh no!")
        flow = Flow("test", tasks=[RaiseOnLoad(exc)])
        s = flow_to_bytes_pickle(flow)

        if version_mismatch:
            monkeypatch.setattr(prefect, "__version__", "0.0.1")
            monkeypatch.setattr(cloudpickle, "__version__", "0.0.2")

        with pytest.raises(
            FlowStorageError, match="An error occurred while unpickling"
        ) as exc:
            flow_from_bytes_pickle(s)

        msg = "mymodule" if import_error else "Oh no!"
        assert msg in str(exc.value)

        # Extra components only present if relevant
        assert ("missing Python module" in str(exc.value)) == import_error
        assert ("version mismatches" in str(exc.value)) == version_mismatch
