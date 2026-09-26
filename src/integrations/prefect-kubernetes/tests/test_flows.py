import pytest
from kubernetes_asyncio.client import models
from prefect_kubernetes.exceptions import KubernetesJobTimeoutError
from prefect_kubernetes.flows import run_namespaced_job, run_namespaced_job_async

from prefect import flow


async def test_run_namespaced_job_timeout_respected(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_read_namespaced_job,
    mock_list_namespaced_pod,
    read_pod_logs,
    successful_job_status,
):
    successful_job_status.status.active = 1
    successful_job_status.status.succeeded = None
    successful_job_status.status.conditions = []
    mock_read_namespaced_job.return_value = successful_job_status

    valid_kubernetes_job_block.timeout_seconds = 1

    with pytest.raises(KubernetesJobTimeoutError):
        await run_namespaced_job_async(kubernetes_job=valid_kubernetes_job_block)

    assert mock_create_namespaced_job.call_count == 1
    assert mock_create_namespaced_job.call_args[1]["namespace"] == "default"
    assert (
        mock_create_namespaced_job.call_args[1]["body"].get("metadata").get("name")
        == "pi"
    )

    assert mock_read_namespaced_job.call_count == 1


async def test_run_namespaced_job_successful(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_read_namespaced_job,
    mock_delete_namespaced_job,
    mock_list_namespaced_pod,
    read_pod_logs,
):
    await run_namespaced_job_async(kubernetes_job=valid_kubernetes_job_block)

    assert mock_create_namespaced_job.call_count == 1
    assert mock_create_namespaced_job.call_args[1]["namespace"] == "default"
    assert (
        mock_create_namespaced_job.call_args[1]["body"].get("metadata").get("name")
        == "pi"
    )

    assert read_pod_logs.call_count == 1

    assert mock_read_namespaced_job.call_count == 1

    assert mock_delete_namespaced_job.call_count == 1


async def test_run_namespaced_job_successful_no_delete_after_completion(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_read_namespaced_job,
    mock_delete_namespaced_job,
    successful_job_status,
    mock_list_namespaced_pod,
    read_pod_logs,
):
    mock_read_namespaced_job.return_value = successful_job_status

    valid_kubernetes_job_block.delete_after_completion = False

    await run_namespaced_job_async(kubernetes_job=valid_kubernetes_job_block)

    assert mock_create_namespaced_job.call_count == 1
    assert mock_create_namespaced_job.call_args[1]["namespace"] == "default"
    assert (
        mock_create_namespaced_job.call_args[1]["body"].get("metadata").get("name")
        == "pi"
    )

    assert mock_read_namespaced_job.call_count == 1

    assert mock_delete_namespaced_job.call_count == 0


async def test_run_namespaced_job_unsuccessful(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_read_namespaced_job,
    mock_delete_namespaced_job,
    unsuccessful_job_status,
    mock_list_namespaced_pod,
    read_pod_logs,
):
    mock_read_namespaced_job.return_value = unsuccessful_job_status

    with pytest.raises(RuntimeError, match=", check the Kubernetes pod logs"):
        await run_namespaced_job_async(kubernetes_job=valid_kubernetes_job_block)

    assert mock_create_namespaced_job.call_count == 1
    assert mock_create_namespaced_job.call_args[1]["namespace"] == "default"
    assert (
        mock_create_namespaced_job.call_args[1]["body"].get("metadata").get("name")
        == "pi"
    )

    assert mock_read_namespaced_job.call_count == 1

    assert mock_delete_namespaced_job.call_count == 0


def test_run_namespaced_job_sync_subflow(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_read_namespaced_job,
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
    assert (
        mock_create_namespaced_job.call_args[1]["body"].get("metadata").get("name")
        == "pi"
    )

    assert read_pod_logs.call_count == 1

    assert mock_read_namespaced_job.call_count == 1

    assert mock_delete_namespaced_job.call_count == 1


async def test_run_namespaced_job_successful_with_evictions(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_read_namespaced_job,
    mock_delete_namespaced_job,
    successful_job_status,
    mock_list_namespaced_pod,
    read_pod_logs,
):
    successful_job_status.status.active = 0
    successful_job_status.status.failed = 1
    mock_read_namespaced_job.return_value = successful_job_status

    await run_namespaced_job_async(kubernetes_job=valid_kubernetes_job_block)

    assert mock_create_namespaced_job.call_count == 1
    assert mock_create_namespaced_job.call_args[1]["namespace"] == "default"
    assert (
        mock_create_namespaced_job.call_args[1]["body"].get("metadata").get("name")
        == "pi"
    )

    assert read_pod_logs.call_count == 1

    assert mock_read_namespaced_job.call_count == 1

    assert mock_delete_namespaced_job.call_count == 1


def test_run_namespaced_job_sync_stream_logs(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_read_namespaced_job,
    mock_delete_namespaced_job,
    successful_job_status,
    mock_list_namespaced_pod,
    read_pod_logs,
    mock_pod_log,
    capsys,
):
    @flow
    def test_sync_flow():
        return run_namespaced_job(
            kubernetes_job=valid_kubernetes_job_block, print_func=print
        )

    test_sync_flow()

    assert mock_create_namespaced_job.call_count == 1
    assert mock_create_namespaced_job.call_args[1]["namespace"] == "default"
    assert (
        mock_create_namespaced_job.call_args[1]["body"].get("metadata").get("name")
        == "pi"
    )

    assert read_pod_logs.call_count == 1

    assert mock_read_namespaced_job.call_count == 1

    assert mock_delete_namespaced_job.call_count == 1

    assert capsys.readouterr().out == "test log\n"


def _job_with_status(status: models.V1JobStatus) -> models.V1Job:
    return models.V1Job(
        metadata=models.V1ObjectMeta(name="test"),
        spec=models.V1JobSpec(
            template=models.V1PodTemplateSpec(
                metadata=models.V1ObjectMeta(labels={"controller-uid": "test-uid"}),
                spec=models.V1PodSpec(containers=[models.V1Container(name="test")]),
            )
        ),
        status=status,
    )


def _pod_list(phase: str) -> models.V1PodList:
    return models.V1PodList(
        items=[
            models.V1Pod(
                metadata=models.V1ObjectMeta(name="test-pod"),
                status=models.V1PodStatus(phase=phase),
            )
        ]
    )


@pytest.fixture
def running_then_succeeded_job(
    mock_read_namespaced_job, mock_list_namespaced_pod, read_pod_logs
):
    """A job observed as active with a running pod, then complete with a finished pod.

    The pod writes more logs between the two observations.
    """
    observations = iter(
        [
            (
                _job_with_status(models.V1JobStatus(active=1)),
                "Running",
                "partial logs\n",
            ),
            (
                _job_with_status(
                    models.V1JobStatus(
                        active=0,
                        failed=0,
                        succeeded=1,
                        conditions=[
                            models.V1JobCondition(type="Complete", status="True")
                        ],
                    )
                ),
                "Succeeded",
                "partial logs\nfinal logs\n",
            ),
        ]
    )
    current = {}

    async def read_job(*args, **kwargs):
        job, pod_phase, pod_log = next(observations)
        current.update(pod_phase=pod_phase, pod_log=pod_log)
        return job

    async def list_pods(*args, **kwargs):
        return _pod_list(current["pod_phase"])

    async def read_log(*args, **kwargs):
        return current["pod_log"]

    mock_read_namespaced_job.side_effect = read_job
    mock_list_namespaced_pod.side_effect = list_pods
    read_pod_logs.side_effect = read_log


async def test_run_namespaced_job_returns_logs_written_after_pod_starts_running(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_delete_namespaced_job,
    running_then_succeeded_job,
    read_pod_logs,
):
    valid_kubernetes_job_block.interval_seconds = 0

    pod_logs = await run_namespaced_job_async(kubernetes_job=valid_kubernetes_job_block)

    assert pod_logs == {"test-pod": "partial logs\nfinal logs\n"}
    assert read_pod_logs.call_count == 1


async def test_run_namespaced_job_streams_logs_before_job_completes(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_delete_namespaced_job,
    running_then_succeeded_job,
    read_pod_logs,
    mock_pod_log,
    capsys,
):
    valid_kubernetes_job_block.interval_seconds = 0

    pod_logs = await run_namespaced_job_async(
        kubernetes_job=valid_kubernetes_job_block, print_func=print
    )

    assert capsys.readouterr().out == "test log\n"
    assert pod_logs == {"test-pod": "partial logs\n"}
    assert read_pod_logs.call_count == 1
