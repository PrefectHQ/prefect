import os
import tempfile

import pytest

import prefect
from prefect import Flow
from prefect.environments import LocalEnvironment
from prefect.environments.storage import Docker, Local
from prefect.utilities.storage import get_flow_image, extract_flow_from_file


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
    flow = Flow("test", environment=LocalEnvironment(), storage=Local(),)
    with pytest.raises(ValueError):
        image = get_flow_image(flow=flow)


def test_extract_flow_from_file():
    with tempfile.TemporaryDirectory() as tmpdir:

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


def test_extract_flow_from_file_raises_on_run_register():
    with tempfile.TemporaryDirectory() as tmpdir:

        contents = """from prefect import Flow\nf=Flow('test-flow')\nf.run()"""

        full_path = os.path.join(tmpdir, "flow.py")

        with open(full_path, "w") as f:
            f.write(contents)

        with prefect.context({"function_gate": True}):
            with pytest.raises(RuntimeError):
                extract_flow_from_file(file_path=full_path)

        contents = """from prefect import Flow\nf=Flow('test-flow')\nf.register()"""

        full_path = os.path.join(tmpdir, "flow.py")

        with open(full_path, "w") as f:
            f.write(contents)

        with prefect.context({"function_gate": True}):
            with pytest.raises(RuntimeError):
                extract_flow_from_file(file_path=full_path)
