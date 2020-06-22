import pytest

from prefect.environments import LocalEnvironment
from prefect.environments.storage import Docker, Local
from prefect.utilities.agent import get_flow_image
from prefect.utilities.graphql import GraphQLResult


def test_get_flow_image_docker_storage():
    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Docker(
                        registry_url="test", image_name="name", image_tag="tag"
                    ).serialize(),
                    "environment": LocalEnvironment().serialize(),
                    "id": "id",
                }
            ),
            "id": "id",
        }
    )
    image = get_flow_image(flow_run=flow_run)
    assert image == "test/name:tag"


def test_get_flow_image_env_metadata():
    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Local().serialize(),
                    "environment": LocalEnvironment(
                        metadata={"image": "repo/name:tag"}
                    ).serialize(),
                    "id": "id",
                }
            ),
            "id": "id",
        }
    )
    image = get_flow_image(flow_run=flow_run)
    assert image == "repo/name:tag"


def test_get_flow_image_raises_on_missing_info():
    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Local().serialize(),
                    "environment": LocalEnvironment().serialize(),
                    "id": "id",
                }
            ),
            "id": "id",
        }
    )
    with pytest.raises(ValueError):
        image = get_flow_image(flow_run=flow_run)
