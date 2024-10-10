from pathlib import Path

import pytest
from kubernetes_asyncio.client.exceptions import ApiValueError
from kubernetes_asyncio.client.models import V1Job
from prefect_kubernetes.jobs import (
    KubernetesJob,
    create_namespaced_job,
    delete_namespaced_job,
    list_namespaced_job,
    patch_namespaced_job,
    read_namespaced_job,
    read_namespaced_job_status,
    replace_namespaced_job,
)


async def test_null_body_raises_error(kubernetes_credentials):
    with pytest.raises(ApiValueError):
        await create_namespaced_job.fn(
            new_job=None, kubernetes_credentials=kubernetes_credentials
        )
    with pytest.raises(ApiValueError):
        await patch_namespaced_job.fn(
            job_updates=None, job_name="", kubernetes_credentials=kubernetes_credentials
        )
    with pytest.raises(ApiValueError):
        await replace_namespaced_job.fn(
            new_job=None, job_name="", kubernetes_credentials=kubernetes_credentials
        )


async def test_create_namespaced_job(kubernetes_credentials, _mock_api_batch_client):
    await create_namespaced_job.fn(
        new_job=V1Job(metadata={"name": "test-job"}),
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )

    assert _mock_api_batch_client.return_value.create_namespaced_job.call_args[1][
        "body"
    ].metadata == {"name": "test-job"}
    assert (
        _mock_api_batch_client.return_value.create_namespaced_job.call_args[1]["a"]
        == "test"
    )


async def test_delete_namespaced_job(kubernetes_credentials, _mock_api_batch_client):
    await delete_namespaced_job.fn(
        job_name="test-job",
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )
    assert (
        _mock_api_batch_client.return_value.delete_namespaced_job.call_args[1]["name"]
        == "test-job"
    )
    assert (
        _mock_api_batch_client.return_value.delete_namespaced_job.call_args[1]["a"]
        == "test"
    )


async def test_list_namespaced_job(kubernetes_credentials, _mock_api_batch_client):
    await list_namespaced_job.fn(
        namespace="ns",
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )
    assert (
        _mock_api_batch_client.return_value.list_namespaced_job.call_args[1][
            "namespace"
        ]
        == "ns"
    )
    assert (
        _mock_api_batch_client.return_value.list_namespaced_job.call_args[1]["a"]
        == "test"
    )


async def test_patch_namespaced_job(kubernetes_credentials, _mock_api_batch_client):
    await patch_namespaced_job.fn(
        job_updates=V1Job(metadata={"name": "test-job"}),
        job_name="test-job",
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )
    assert _mock_api_batch_client.return_value.patch_namespaced_job.call_args[1][
        "body"
    ].metadata == {"name": "test-job"}
    assert (
        _mock_api_batch_client.return_value.patch_namespaced_job.call_args[1]["name"]
        == "test-job"
    )
    assert (
        _mock_api_batch_client.return_value.patch_namespaced_job.call_args[1]["a"]
        == "test"
    )


async def test_read_namespaced_job(kubernetes_credentials, _mock_api_batch_client):
    await read_namespaced_job.fn(
        job_name="test-job",
        namespace="ns",
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )
    assert (
        _mock_api_batch_client.return_value.read_namespaced_job.call_args[1]["name"]
        == "test-job"
    )
    assert (
        _mock_api_batch_client.return_value.read_namespaced_job.call_args[1][
            "namespace"
        ]
        == "ns"
    )
    assert (
        _mock_api_batch_client.return_value.read_namespaced_job.call_args[1]["a"]
        == "test"
    )


async def test_replace_namespaced_job(kubernetes_credentials, _mock_api_batch_client):
    await replace_namespaced_job.fn(
        job_name="test-job",
        new_job=V1Job(metadata={"name": "test-job"}),
        namespace="ns",
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )
    assert (
        _mock_api_batch_client.return_value.replace_namespaced_job.call_args[1]["name"]
        == "test-job"
    )
    assert (
        _mock_api_batch_client.return_value.replace_namespaced_job.call_args[1][
            "namespace"
        ]
        == "ns"
    )
    assert _mock_api_batch_client.return_value.replace_namespaced_job.call_args[1][
        "body"
    ].metadata == {"name": "test-job"}
    assert (
        _mock_api_batch_client.return_value.replace_namespaced_job.call_args[1]["a"]
        == "test"
    )


async def test_read_namespaced_job_status(
    kubernetes_credentials, _mock_api_batch_client
):
    await read_namespaced_job_status.fn(
        job_name="test-job",
        namespace="ns",
        a="test",
        kubernetes_credentials=kubernetes_credentials,
    )
    assert (
        _mock_api_batch_client.return_value.read_namespaced_job_status.call_args[1][
            "name"
        ]
        == "test-job"
    )
    assert (
        _mock_api_batch_client.return_value.read_namespaced_job_status.call_args[1][
            "namespace"
        ]
        == "ns"
    )
    assert (
        _mock_api_batch_client.return_value.read_namespaced_job_status.call_args[1]["a"]
        == "test"
    )


async def test_job_block_from_job_yaml(kubernetes_credentials):
    DIR = (
        (
            Path.cwd()
            / "src"
            / "integrations"
            / "prefect-kubernetes"
            / "tests"
            / "sample_k8s_resources"
            / "sample_job.yaml"
        )
        if Path.cwd().name == "prefect"
        else Path.cwd() / "tests" / "sample_k8s_resources" / "sample_job.yaml"
    )
    job = KubernetesJob.from_yaml_file(
        credentials=kubernetes_credentials,
        manifest_path=DIR,
    )
    assert isinstance(job, KubernetesJob)
    assert job.v1_job["metadata"]["name"] == "pi"


async def test_job_block_wait_never_called_raises(
    valid_kubernetes_job_block,
    mock_create_namespaced_job,
    mock_delete_namespaced_job,
):
    job_run = await valid_kubernetes_job_block.trigger()

    with pytest.raises(
        ValueError, match="The Kubernetes Job run is not in a completed state"
    ):
        await job_run.fetch_result()


async def test_job_block_generates_default_credentials():
    job_block = KubernetesJob(v1_job=dict(metadata=dict(name="test-job")))
    assert job_block.credentials is not None
    assert job_block.credentials.cluster_config is None
