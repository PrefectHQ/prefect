from functools import partial
from unittest.mock import MagicMock

import pytest

import prefect
from prefect.infrastructure import (
    DockerContainer,
    Infrastructure,
    KubernetesJob,
    Process,
)
from prefect.infrastructure.submission import (
    FLOW_RUN_ENTRYPOINT,
    base_flow_run_environment,
    base_flow_run_labels,
    submit_flow_run,
)


@pytest.fixture(autouse=True)
def reset_mock_infrastructure():
    MockInfrastructure._run.reset_mock()
    yield


class MockInfrastructure(Infrastructure):
    type: str = "mock"

    _run = MagicMock()

    async def run(self, task_status=None):
        if task_status:
            task_status.started()
        self._run(self.dict())

    class Config:
        arbitrary_types_allowed = True


@pytest.mark.usefixtures("use_hosted_orion")
@pytest.mark.parametrize(
    "infrastructure_type",
    [
        pytest.param(
            # This allows testing of against Kubernetes running in Docker Desktop
            partial(KubernetesJob, _api_dns_name="host.docker.internal"),
            marks=pytest.mark.service("kubernetes"),
            id="kubernetes-job",
        ),
        pytest.param(
            DockerContainer,
            marks=pytest.mark.service("docker"),
            id="docker-container",
        ),
        pytest.param(Process, id="process"),
    ],
)
async def test_flow_run_by_infrastructure_type(
    deployment,
    infrastructure_type,
    orion_client,
):
    flow_run = await orion_client.create_flow_run_from_deployment(deployment.id)
    result = await submit_flow_run(flow_run, infrastructure=infrastructure_type())

    flow_run = await orion_client.read_flow_run(flow_run.id)
    assert flow_run.state.is_completed(), flow_run.state.message

    assert result.status_code == 0


async def test_submission_adds_flow_run_metadata(
    deployment,
    orion_client,
):
    flow_run = await orion_client.create_flow_run_from_deployment(deployment.id)
    await submit_flow_run(flow_run, infrastructure=MockInfrastructure())
    MockInfrastructure._run.assert_called_once_with(
        {
            "type": "mock",
            "env": {"PREFECT__FLOW_RUN_ID": flow_run.id.hex},
            "labels": {
                "prefect.io/flow-run-id": str(flow_run.id),
                "prefect.io/flow-run-name": flow_run.name,
                "prefect.io/version": prefect.__version__,
            },
            "name": flow_run.name,
            "command": FLOW_RUN_ENTRYPOINT,
        }
    )


async def test_submission_does_not_mutate_original_object(
    deployment,
    orion_client,
):
    flow_run = await orion_client.create_flow_run_from_deployment(deployment.id)
    obj = MockInfrastructure()
    await submit_flow_run(flow_run, infrastructure=obj)
    assert obj.env == {}
    assert obj.command is None
    assert obj.labels == {}
    assert obj.name is None


async def test_submission_does_not_override_existing_command(
    deployment,
    orion_client,
):
    flow_run = await orion_client.create_flow_run_from_deployment(deployment.id)
    await submit_flow_run(flow_run, infrastructure=MockInfrastructure(command=["test"]))
    MockInfrastructure._run.call_args[0][0]["command"] == ["test"]


async def test_submission_does_not_override_existing_env(
    deployment,
    orion_client,
):
    flow_run = await orion_client.create_flow_run_from_deployment(deployment.id)
    await submit_flow_run(
        flow_run, infrastructure=MockInfrastructure(env={"foo": "bar"})
    )
    MockInfrastructure._run.call_args[0][0]["env"] == {
        **base_flow_run_environment(flow_run),
        "foo": "bar",
    }


async def test_submission_does_not_override_existing_labels(
    deployment,
    orion_client,
):
    flow_run = await orion_client.create_flow_run_from_deployment(deployment.id)
    await submit_flow_run(
        flow_run, infrastructure=MockInfrastructure(labels={"foo": "bar"})
    )
    MockInfrastructure._run.call_args[0][0]["labels"] == {
        **base_flow_run_labels(flow_run),
        "foo": "bar",
    }


async def test_submission_does_not_override_existing_name(
    deployment,
    orion_client,
):
    flow_run = await orion_client.create_flow_run_from_deployment(deployment.id)
    await submit_flow_run(flow_run, infrastructure=MockInfrastructure(name="test"))
    MockInfrastructure._run.call_args[0][0]["name"] == "test"
