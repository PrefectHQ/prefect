from functools import partial

import pytest

from prefect.infrastructure import DockerContainer, KubernetesJob, Process
from prefect.infrastructure.submission import submit_flow_run


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
