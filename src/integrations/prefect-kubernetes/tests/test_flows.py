import pytest
from prefect_kubernetes.exceptions import KubernetesJobTimeoutError
from prefect_kubernetes.flows import run_namespaced_job

from prefect import flow


async def test_run_namespaced_job_timeout_respected(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_read_namespaced_job_status,
    mock_list_namespaced_pod,
    read_pod_logs,
    successful_job_status,
):
    successful_job_status.status.active = 1
    successful_job_status.status.succeeded = None
    successful_job_status.status.conditions = []
    mock_read_namespaced_job_status.return_value = successful_job_status

    valid_kubernetes_job_block.timeout_seconds = 1

    with pytest.raises(KubernetesJobTimeoutError):
        await run_namespaced_job(kubernetes_job=valid_kubernetes_job_block)

    assert mock_create_namespaced_job.call_count == 1
    assert mock_create_namespaced_job.call_args[1]["namespace"] == "default"
    assert mock_create_namespaced_job.call_args[1]["body"].metadata.name == "pi"

    assert mock_read_namespaced_job_status.call_count == 1


async def test_run_namespaced_job_successful(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_read_namespaced_job_status,
    mock_delete_namespaced_job,
    mock_list_namespaced_pod,
    read_pod_logs,
):
    await run_namespaced_job(kubernetes_job=valid_kubernetes_job_block)

    assert mock_create_namespaced_job.call_count == 1
    assert mock_create_namespaced_job.call_args[1]["namespace"] == "default"
    assert mock_create_namespaced_job.call_args[1]["body"].metadata.name == "pi"

    assert read_pod_logs.call_count == 1

    assert mock_read_namespaced_job_status.call_count == 1

    assert mock_delete_namespaced_job.call_count == 1


async def test_run_namespaced_job_successful_no_delete_after_completion(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_read_namespaced_job_status,
    mock_delete_namespaced_job,
    successful_job_status,
    mock_list_namespaced_pod,
    read_pod_logs,
):
    mock_read_namespaced_job_status.return_value = successful_job_status

    valid_kubernetes_job_block.delete_after_completion = False

    await run_namespaced_job(kubernetes_job=valid_kubernetes_job_block)

    assert mock_create_namespaced_job.call_count == 1
    assert mock_create_namespaced_job.call_args[1]["namespace"] == "default"
    assert mock_create_namespaced_job.call_args[1]["body"].metadata.name == "pi"

    assert mock_read_namespaced_job_status.call_count == 1

    assert mock_delete_namespaced_job.call_count == 0


async def test_run_namespaced_job_unsuccessful(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_read_namespaced_job_status,
    mock_delete_namespaced_job,
    unsuccessful_job_status,
    mock_list_namespaced_pod,
    read_pod_logs,
):
    mock_read_namespaced_job_status.return_value = unsuccessful_job_status

    with pytest.raises(RuntimeError, match=", check the Kubernetes pod logs"):
        await run_namespaced_job(kubernetes_job=valid_kubernetes_job_block)

    assert mock_create_namespaced_job.call_count == 1
    assert mock_create_namespaced_job.call_args[1]["namespace"] == "default"
    assert mock_create_namespaced_job.call_args[1]["body"].metadata.name == "pi"

    assert mock_read_namespaced_job_status.call_count == 1

    assert mock_delete_namespaced_job.call_count == 0


def test_run_namespaced_job_sync_subflow(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_read_namespaced_job_status,
    mock_delete_namespaced_job,
    successful_job_status,
    mock_list_namespaced_pod,
    read_pod_logs,
):
    @flow
    def test_sync_flow():
        return run_namespaced_job(kubernetes_job=valid_kubernetes_job_block)

    test_sync_flow()

    assert mock_create_namespaced_job.call_count == 1
    assert mock_create_namespaced_job.call_args[1]["namespace"] == "default"
    assert mock_create_namespaced_job.call_args[1]["body"].metadata.name == "pi"

    assert read_pod_logs.call_count == 1

    assert mock_read_namespaced_job_status.call_count == 1

    assert mock_delete_namespaced_job.call_count == 1


async def test_run_namespaced_job_successful_with_evictions(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_read_namespaced_job_status,
    mock_delete_namespaced_job,
    successful_job_status,
    mock_list_namespaced_pod,
    read_pod_logs,
):
    successful_job_status.status.active = 0
    successful_job_status.status.failed = 1
    mock_read_namespaced_job_status.return_value = successful_job_status

    await run_namespaced_job(kubernetes_job=valid_kubernetes_job_block)

    assert mock_create_namespaced_job.call_count == 1
    assert mock_create_namespaced_job.call_args[1]["namespace"] == "default"
    assert mock_create_namespaced_job.call_args[1]["body"].metadata.name == "pi"

    assert read_pod_logs.call_count == 1

    assert mock_read_namespaced_job_status.call_count == 1

    assert mock_delete_namespaced_job.call_count == 1
