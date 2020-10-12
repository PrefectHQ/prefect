import os
import tempfile

import pytest

import prefect
from prefect import Flow
from prefect.environments import LocalEnvironment
from prefect.environments.storage import Docker, Local
from prefect.utilities.storage import (
    get_flow_image,
    extract_flow_from_file,
    extract_flow_from_module,
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
        image = get_flow_image(flow=flow)


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
