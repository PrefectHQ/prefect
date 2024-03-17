import pytest
from anyio.abc._tasks import TaskStatus

from prefect._internal.compatibility.deprecated import PrefectDeprecationWarning
from prefect.infrastructure.base import Infrastructure, InfrastructureResult
from prefect.infrastructure.container import (
    DockerContainer,
    DockerRegistry,
)
from prefect.infrastructure.kubernetes import KubernetesJob
from prefect.infrastructure.process import Process


class PretendInfrastructure(Infrastructure):
    type = "Pretend"

    async def run(self, task_status: TaskStatus = None) -> InfrastructureResult:
        return await super().run(task_status)

    async def kill_infrastructure(self) -> None:
        await super().kill_infrastructure()

    def preview(self) -> str:
        return super().preview()


@pytest.mark.parametrize(
    "InfraBlock, expected_message",
    [
        (
            PretendInfrastructure,
            "prefect.infrastructure.base.Infrastructure has been deprecated."
            " It will not be available after Sep 2024."
            " Use the `BaseWorker` class to create custom infrastructure integrations instead."
            " Refer to the upgrade guide for more information",
        ),
        (
            KubernetesJob,
            "prefect.infrastructure.kubernetes.KubernetesJob has been deprecated."
            " It will not be available after Sep 2024."
            " Use the Kubernetes worker from prefect-kubernetes instead."
            " Refer to the upgrade guide for more information",
        ),
        (
            DockerContainer,
            "prefect.infrastructure.container.DockerContainer has been deprecated."
            " It will not be available after Sep 2024."
            " Use the Docker worker from prefect-docker instead."
            " Refer to the upgrade guide for more information",
        ),
        (
            Process,
            "prefect.infrastructure.process.Process has been deprecated."
            " It will not be available after Sep 2024."
            " Use the process worker instead."
            " Refer to the upgrade guide for more information",
        ),
    ],
)
def test_infra_blocks_emit_a_deprecation_warning(InfraBlock, expected_message):
    with pytest.warns(PrefectDeprecationWarning, match=expected_message):
        InfraBlock()


def test_docker_registry_emits_a_deprecation_warning():
    with pytest.warns(
        PrefectDeprecationWarning,
        match=(
            "prefect.infrastructure.container.DockerRegistry has been deprecated."
            " It will not be available after Sep 2024."
            " Use the `DockerRegistryCredentials` class from prefect-docker instead."
        ),
    ):
        DockerRegistry(username="foo", password="bar", registry_url="baz")
