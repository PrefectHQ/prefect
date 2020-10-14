import pytest

from prefect.environments import LocalEnvironment
from prefect.environments.storage import Docker, Local
from prefect.run_configs import KubernetesRun
from prefect.utilities.agent import get_flow_image, get_flow_run_command
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
        get_flow_image(flow_run=flow_run)


def test_get_flow_image_run_config_docker_storage():
    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Docker(
                        registry_url="test", image_name="name", image_tag="tag"
                    ).serialize(),
                    "run_config": KubernetesRun().serialize(),
                    "id": "id",
                }
            ),
            "id": "id",
        }
    )
    image = get_flow_image(flow_run)
    assert image == "test/name:tag"


def test_get_flow_image_run_config_default_value_from_core_version():
    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "core_version": "0.13.0",
                    "storage": Local().serialize(),
                    "run_config": KubernetesRun().serialize(),
                    "id": "id",
                }
            ),
            "id": "id",
        }
    )
    image = get_flow_image(flow_run)
    assert image == "prefecthq/prefect:all_extras-0.13.0"


def test_get_flow_image_run_config_image_on_RunConfig():
    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Local().serialize(),
                    "run_config": KubernetesRun(image="myfancyimage").serialize(),
                    "id": "id",
                }
            ),
            "id": "id",
        }
    )
    image = get_flow_image(flow_run)
    assert image == "myfancyimage"


@pytest.mark.parametrize(
    "core_version,command",
    [
        ("0.10.0", "prefect execute cloud-flow"),
        ("0.6.0+134", "prefect execute cloud-flow"),
        ("0.13.0", "prefect execute flow-run"),
        ("0.13.1+134", "prefect execute flow-run"),
    ],
)
def test_get_flow_run_command(core_version, command):
    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Local().serialize(),
                    "environment": LocalEnvironment().serialize(),
                    "id": "id",
                    "core_version": core_version,
                }
            ),
            "id": "id",
        }
    )

    assert get_flow_run_command(flow_run) == command


def test_get_flow_run_command_works_if_core_version_not_on_response():
    legacy_command = "prefect execute cloud-flow"
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

    assert get_flow_run_command(flow_run) == legacy_command
