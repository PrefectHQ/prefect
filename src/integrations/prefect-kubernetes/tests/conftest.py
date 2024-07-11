from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml
from kubernetes_asyncio.client import (
    AppsV1Api,
    BatchV1Api,
    CoreV1Api,
    CustomObjectsApi,
    models,
)
from kubernetes_asyncio.client.exceptions import ApiException
from prefect_kubernetes.credentials import KubernetesCredentials
from prefect_kubernetes.jobs import KubernetesJob

from prefect.settings import PREFECT_LOGGING_TO_API_ENABLED, temporary_settings
from prefect.testing.utilities import prefect_test_harness

BASEDIR = (
    Path.cwd() / "src" / "integrations" / "prefect-kubernetes" / "tests"
    if Path.cwd().name == "prefect"
    else Path.cwd() / "tests"
)
GOOD_CONFIG_FILE_PATH = BASEDIR / "kube_config.yaml"


@pytest.fixture(scope="session", autouse=True)
def prefect_db():
    """
    Sets up test harness for temporary DB during test runs.
    """
    try:
        with prefect_test_harness():
            yield
    except OSError as e:
        if "Directory not empty" in str(e):
            pass
        else:
            raise e


@pytest.fixture(scope="session", autouse=True)
def disable_api_logging():
    """
    Disables API logging for all tests.
    """
    with temporary_settings(updates={PREFECT_LOGGING_TO_API_ENABLED: False}):
        yield


@pytest.fixture
def kube_config_dict():
    return yaml.safe_load(GOOD_CONFIG_FILE_PATH.read_text())


@pytest.fixture
def successful_job_status():
    job_status = MagicMock()
    job_status.status.active = None
    job_status.status.failed = None
    job_status.status.succeeded = 1
    job_status.status.conditions = [
        models.V1JobCondition(type="Complete", status="True"),
    ]
    return job_status


@pytest.fixture
def unsuccessful_job_status():
    job_status = MagicMock()
    job_status.status.active = 0
    job_status.status.failed = 1
    job_status.status.succeeded = 1
    job_status.status.conditions = [
        models.V1JobCondition(
            type="Failed", status="True", reason="BackoffLimitExceeded"
        ),
    ]
    return job_status


@pytest.fixture
def kubernetes_credentials(kube_config_dict):
    return KubernetesCredentials(
        cluster_config=dict(context_name="test", config=kube_config_dict)
    )


@pytest.fixture
def _mock_api_app_client(monkeypatch):
    app_client = AsyncMock(spec=AppsV1Api)
    monkeypatch.setattr(
        "prefect_kubernetes.credentials.KubernetesCredentials.get_resource_specific_client",
        app_client,
    )
    return app_client


@pytest.fixture
async def _mock_api_batch_client(monkeypatch):
    batch_client = AsyncMock(spec=BatchV1Api)

    monkeypatch.setattr(
        "prefect_kubernetes.credentials.KubernetesCredentials.get_resource_specific_client",
        batch_client,
    )

    return batch_client


@pytest.fixture
def _mock_api_core_client(monkeypatch):
    core_client = AsyncMock(spec=CoreV1Api)

    monkeypatch.setattr(
        "prefect_kubernetes.credentials.KubernetesCredentials.get_resource_specific_client",
        core_client,
    )
    return core_client


@pytest.fixture
def _mock_api_custom_objects_client(monkeypatch):
    custom_objects_client = AsyncMock(spec=CustomObjectsApi)

    monkeypatch.setattr(
        "prefect_kubernetes.credentials.KubernetesCredentials.get_resource_specific_client",
        custom_objects_client,
    )

    return custom_objects_client


@pytest.fixture
def mock_create_namespaced_job(monkeypatch):
    mock_v1_job = AsyncMock(
        return_value=models.V1Job(metadata=models.V1ObjectMeta(name="test"))
    )
    monkeypatch.setattr(
        "kubernetes_asyncio.client.api.BatchV1Api.create_namespaced_job", mock_v1_job
    )
    return mock_v1_job


@pytest.fixture
def mock_read_namespaced_job_status(monkeypatch):
    mock_v1_job_status = AsyncMock(
        return_value=models.V1Job(
            metadata=models.V1ObjectMeta(
                name="test", labels={"controller-uid": "test"}
            ),
            spec=models.V1JobSpec(
                template=models.V1PodTemplateSpec(
                    spec=models.V1PodSpec(containers=[models.V1Container(name="test")])
                )
            ),
            status=models.V1JobStatus(
                active=0,
                failed=0,
                succeeded=1,
                conditions=[
                    models.V1JobCondition(type="Complete", status="True"),
                ],
            ),
        )
    )
    monkeypatch.setattr(
        "kubernetes_asyncio.client.BatchV1Api.read_namespaced_job_status",
        mock_v1_job_status,
    )
    return mock_v1_job_status


@pytest.fixture
def mock_delete_namespaced_job(monkeypatch):
    mock_v1_job = AsyncMock(
        return_value=models.V1Job(metadata=models.V1ObjectMeta(name="test"))
    )
    monkeypatch.setattr(
        "kubernetes_asyncio.client.BatchV1Api.delete_namespaced_job", mock_v1_job
    )
    return mock_v1_job


@pytest.fixture
def mock_stream_timeout(monkeypatch):
    monkeypatch.setattr(
        "kubernetes_asyncio.watch.Watch.stream",
        MagicMock(side_effect=ApiException(status=408)),
    )


@pytest.fixture
def mock_pod_log(monkeypatch):
    async def pod_log(*args, **kwargs):
        yield "test log"

    monkeypatch.setattr(
        "kubernetes_asyncio.watch.Watch.stream",
        MagicMock(side_effect=pod_log),
    )


@pytest.fixture
def mock_list_namespaced_pod(monkeypatch):
    result = models.V1PodList(
        items=[
            models.V1Pod(
                metadata=models.V1ObjectMeta(name="test-pod"),
                status=models.V1PodStatus(phase="Completed"),
            )
        ]
    )
    mock_pod_list = AsyncMock(return_value=result)

    monkeypatch.setattr(
        "kubernetes_asyncio.client.api.CoreV1Api.list_namespaced_pod", mock_pod_list
    )
    return mock_pod_list


@pytest.fixture
def read_pod_logs(monkeypatch):
    pod_log = AsyncMock(return_value="test log")

    monkeypatch.setattr(
        "kubernetes_asyncio.client.api.CoreV1Api.read_namespaced_pod_log", pod_log
    )
    return pod_log


@pytest.fixture
def valid_kubernetes_job_block(kubernetes_credentials):
    with open(BASEDIR / "sample_k8s_resources" / "sample_job.yaml") as f:
        job_dict = yaml.safe_load(f)

    return KubernetesJob(
        credentials=kubernetes_credentials,
        v1_job=job_dict,
    )
