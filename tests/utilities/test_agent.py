import pytest

from prefect.environments import LocalEnvironment
from prefect.storage import Docker, Local
from prefect.run_configs import KubernetesRun, LocalRun
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


@pytest.mark.parametrize("run_config", [KubernetesRun(), LocalRun(), None])
def test_get_flow_image_run_config_docker_storage(run_config):
    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Docker(
                        registry_url="test", image_name="name", image_tag="tag"
                    ).serialize(),
                    "id": "id",
                }
            ),
            "run_config": run_config.serialize() if run_config else None,
            "id": "id",
        }
    )
    image = get_flow_image(flow_run)
    assert image == "test/name:tag"


@pytest.mark.parametrize("run_config", [KubernetesRun(), LocalRun(), None])
@pytest.mark.parametrize("version", ["0.13.0", "0.10.0+182.g385a32514.dirty", None])
@pytest.mark.parametrize("default", [None, "default-value"])
def test_get_flow_image_run_config_default(run_config, version, default):
    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "core_version": version,
                    "storage": Local().serialize(),
                    "id": "id",
                }
            ),
            "run_config": run_config.serialize() if run_config else None,
            "id": "id",
        }
    )
    if default is None:
        expected_version = version.split("+")[0] if version else "latest"
        expected = f"prefecthq/prefect:{expected_version}"
    else:
        expected = default

    image = get_flow_image(flow_run, default=default)
    assert image == expected


def test_get_flow_image_run_config_image_on_RunConfig():
    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Local().serialize(),
                    "id": "id",
                }
            ),
            "run_config": KubernetesRun(image="myfancyimage").serialize(),
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
