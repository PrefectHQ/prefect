import pytest

from prefect import Flow
from prefect.environments import LocalEnvironment
from prefect.environments.storage import Docker, Local
from prefect.utilities.storage import get_flow_image


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
