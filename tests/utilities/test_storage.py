import os

import pytest
import cloudpickle

import prefect
from prefect import Flow, Task
from prefect.environments import LocalEnvironment
from prefect.storage import Docker, Local
from prefect.utilities.exceptions import StorageError
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


def test_extract_flow_from_file(tmpdir):
    contents = """from prefect import Flow\nf=Flow('test-flow')"""

    full_path = os.path.join(tmpdir, "flow.py")

    with open(full_path, "w") as f:
        f.write(contents)

    flow = extract_flow_from_file(file_path=full_path)
    assert flow.run().is_successful()

    flow = extract_flow_from_file(file_contents=contents)
    assert flow.run().is_successful()

    flow = extract_flow_from_file(file_path=full_path, flow_name="test-flow")
    assert flow.run().is_successful()

    with pytest.raises(ValueError):
        extract_flow_from_file(file_path=full_path, flow_name="not-real")

    with pytest.raises(ValueError):
        extract_flow_from_file(file_path=full_path, file_contents=contents)

    with pytest.raises(ValueError):
        extract_flow_from_file()


def test_extract_flow_from_file_raises_on_run_register(tmpdir):
    contents = """from prefect import Flow\nf=Flow('test-flow')\nf.run()"""

    full_path = os.path.join(tmpdir, "flow.py")

    with open(full_path, "w") as f:
        f.write(contents)

    with prefect.context({"loading_flow": True}):
        with pytest.warns(Warning):
            extract_flow_from_file(file_path=full_path)

    contents = """from prefect import Flow\nf=Flow('test-flow')\nf.register()"""

    full_path = os.path.join(tmpdir, "flow.py")

    with open(full_path, "w") as f:
        f.write(contents)

    with prefect.context({"loading_flow": True}):
        with pytest.warns(Warning):
            extract_flow_from_file(file_path=full_path)


flow = Flow("test-module-loading")


def test_extract_flow_from_module():
    module_name = "tests.utilities.test_storage"

    multi_level_flow = Flow("test-module-loading-multilevel")
    factory_flow = Flow("test-module-loading-callable")

    test_extract_flow_from_module.multi_level_flow = multi_level_flow
    test_extract_flow_from_module.not_a_flow = None
    test_extract_flow_from_module.not_a_flow_factory = lambda: object()
    test_extract_flow_from_module.invalid_callable = lambda _a, _b, **_kwargs: None

    class FlowFactory:
        @classmethod
        def default_flow(cls):
            return factory_flow

    test_extract_flow_from_module.callable_flow = FlowFactory.default_flow

    default_flow = extract_flow_from_module(module_name)
    attribute_flow = extract_flow_from_module(module_name, "flow")
    module_flow = extract_flow_from_module(f"{module_name}:flow")
    multi_level_default_flow = extract_flow_from_module(
        f"{module_name}:test_extract_flow_from_module.multi_level_flow"
    )
    multi_level_arg_flow = extract_flow_from_module(
        module_name, "test_extract_flow_from_module.multi_level_flow"
    )
    callable_flow = extract_flow_from_module(
        f"{module_name}:test_extract_flow_from_module.callable_flow"
    )

    assert flow == default_flow == attribute_flow == module_flow
    assert multi_level_flow == multi_level_default_flow == multi_level_arg_flow
    assert factory_flow == callable_flow

    with pytest.raises(AttributeError):
        extract_flow_from_module("tests.utilities.test_storage:should_not_exist_flow")

    with pytest.raises(AttributeError):
        extract_flow_from_module(
            "tests.utilities.test_storage", "should_not_exist_flow"
        )

    with pytest.raises(ValueError, match="without an attribute specifier or remove"):
        extract_flow_from_module("tests.utilities.test_storage:flow", "flow")

    with pytest.raises(ValueError, match="must return `prefect.Flow`"):
        extract_flow_from_module(
            f"{module_name}:test_extract_flow_from_module.not_a_flow"
        )

    with pytest.raises(ValueError, match="must return `prefect.Flow`"):
        extract_flow_from_module(
            f"{module_name}:test_extract_flow_from_module.not_a_flow_factory"
        )

    with pytest.raises(TypeError):
        extract_flow_from_module(
            f"{module_name}:test_extract_flow_from_module.invalid_callable"
        )


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
            StorageError, match="An error occurred while unpickling"
        ) as exc:
            flow_from_bytes_pickle(s)

        msg = "mymodule" if import_error else "Oh no!"
        assert msg in str(exc.value)

        # Extra components only present if relevant
        assert ("missing Python module" in str(exc.value)) == import_error
        assert ("version mismatches" in str(exc.value)) == version_mismatch
