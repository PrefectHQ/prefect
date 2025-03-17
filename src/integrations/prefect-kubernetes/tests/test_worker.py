import base64
import json
import re
import sys
import uuid
from contextlib import asynccontextmanager
from time import monotonic, sleep
from typing import Any
from unittest import mock
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import anyio
import anyio.abc
import kubernetes_asyncio
import pytest
from kubernetes_asyncio.client import ApiClient, BatchV1Api, CoreV1Api, V1Pod
from kubernetes_asyncio.client.exceptions import ApiException
from kubernetes_asyncio.client.models import (
    CoreV1Event,
    CoreV1EventList,
    V1ListMeta,
    V1ObjectMeta,
    V1ObjectReference,
    V1Secret,
)
from kubernetes_asyncio.config import ConfigException
from prefect_kubernetes import KubernetesWorker
from prefect_kubernetes.utilities import (
    KeepAliveClientRequest,
    _slugify_label_value,
    _slugify_name,
)
from prefect_kubernetes.worker import KubernetesWorkerJobConfiguration
from pydantic import ValidationError

import prefect
from prefect.client.schemas import FlowRun
from prefect.client.schemas.actions import WorkPoolCreate, WorkPoolUpdate
from prefect.client.schemas.objects import WorkPool
from prefect.exceptions import (
    InfrastructureError,
)
from prefect.futures import PrefectFlowRunFuture
from prefect.server.schemas.core import Flow
from prefect.server.schemas.responses import DeploymentResponse
from prefect.settings import (
    PREFECT_API_KEY,
    get_current_settings,
    temporary_settings,
)
from prefect.states import Running
from prefect.types._datetime import DateTime, parse_datetime
from prefect.utilities.dockerutils import get_prefect_image_name

FAKE_CLUSTER = "fake-cluster"
MOCK_CLUSTER_UID = "1234"


@pytest.fixture
def mock_watch(monkeypatch: pytest.MonkeyPatch):
    mock = MagicMock(return_value=AsyncMock())
    monkeypatch.setattr("kubernetes_asyncio.watch.Watch", mock)
    return mock


async def mock_stream(*args: Any, **kwargs: Any):
    async for event in mock_pods_stream_that_returns_completed_pod(*args, **kwargs):
        yield event


@pytest.fixture
def mock_cluster_config(monkeypatch: pytest.MonkeyPatch):
    mock = MagicMock()
    # We cannot mock this or the `except` clause will complain
    mock.ConfigException.return_value = ConfigException
    mock.list_kube_config_contexts.return_value = (
        [],
        {"context": {"cluster": FAKE_CLUSTER}},
    )
    mock.new_client_from_config = AsyncMock()
    monkeypatch.setattr("prefect_kubernetes.worker.config", mock)
    monkeypatch.setattr(
        "prefect_kubernetes.worker.config.ConfigException", ConfigException
    )
    return mock


@pytest.fixture
def mock_anyio_sleep_monotonic(monkeypatch: pytest.MonkeyPatch, event_loop: Any):
    def mock_monotonic():
        return mock_sleep.current_time

    async def mock_sleep(duration: float):
        mock_sleep.current_time += duration

    mock_sleep.current_time = monotonic()
    monkeypatch.setattr("time.monotonic", mock_monotonic)
    monkeypatch.setattr("anyio.sleep", mock_sleep)


@pytest.fixture
def mock_job():
    mock = AsyncMock(spec=kubernetes_asyncio.client.V1Job)

    mock.metadata.name = "mock-job"
    mock.metadata.namespace = "mock-namespace"
    return mock


@pytest.fixture
def mock_pod():
    pod = MagicMock(spec=V1Pod)
    pod.status.phase = "Running"
    pod.metadata.name = "mock-pod"
    pod.metadata.namespace = "mock-namespace"
    pod.metadata.uid = "1234"
    return pod


@pytest.fixture
def mock_core_client(monkeypatch: pytest.MonkeyPatch, mock_cluster_config: MagicMock):
    mock = MagicMock(spec=CoreV1Api, return_value=AsyncMock())
    mock.return_value.read_namespace.return_value.metadata.uid = MOCK_CLUSTER_UID
    mock.return_value.list_namespaced_pod.return_value.items.sort = MagicMock()
    mock.return_value.read_namespaced_pod_log.return_value.content.readline = AsyncMock(
        return_value=None
    )

    monkeypatch.setattr(
        "prefect_kubernetes.worker.KubernetesWorker._get_configured_kubernetes_client",
        MagicMock(spec=ApiClient),
    )
    monkeypatch.setattr("prefect_kubernetes.worker.CoreV1Api", mock)
    monkeypatch.setattr("kubernetes_asyncio.client.CoreV1Api", mock)
    return mock


@pytest.fixture
def mock_core_client_lean(monkeypatch: pytest.MonkeyPatch):
    mock = MagicMock(spec=CoreV1Api, return_value=AsyncMock())
    monkeypatch.setattr("prefect_kubernetes.worker.CoreV1Api", mock)
    monkeypatch.setattr("kubernetes_asyncio.client.CoreV1Api", mock)
    mock.return_value.list_namespaced_pod.return_value.items.sort = MagicMock()
    return mock


@pytest.fixture
def mock_batch_client(monkeypatch: pytest.MonkeyPatch, mock_job: MagicMock):
    mock = MagicMock(spec=BatchV1Api, return_value=AsyncMock())

    @asynccontextmanager
    async def get_batch_client(*args: Any, **kwargs: Any):
        yield mock()

    monkeypatch.setattr(
        "prefect_kubernetes.worker.KubernetesWorker._get_batch_client",
        get_batch_client,
    )

    mock.return_value.create_namespaced_job.return_value = mock_job
    monkeypatch.setattr("prefect_kubernetes.worker.BatchV1Api", mock)
    return mock


@pytest.fixture
async def mock_pods_stream_that_returns_running_pod(
    mock_core_client: MagicMock, mock_pod: MagicMock, mock_job: MagicMock
):
    async def mock_stream(*args: Any, **kwargs: Any):
        if kwargs["func"] == mock_core_client.return_value.list_namespaced_pod:
            yield {"object": mock_pod, "type": "MODIFIED"}
        if kwargs["func"] == mock_core_client.return_value.list_namespaced_job:
            mock_job.status.completion_time = DateTime.now("utc").timestamp()
            yield {"object": mock_job, "type": "MODIFIED"}

    return mock_stream


@pytest.fixture
async def mock_pods_stream_that_returns_completed_pod(
    mock_core_client, mock_pod, mock_job
):
    async def mock_stream(*args, **kwargs):
        if kwargs["func"] == mock_core_client.return_value.list_namespaced_pod:
            yield {"object": mock_pod, "type": "MODIFIED"}
        if kwargs["func"] == mock_core_client.return_value.list_namespaced_job:
            mock_job.status.completion_time = True
            mock_job.status.failed = 0
            mock_job.spec.backoff_limit = 6
            yield {"object": mock_job, "type": "MODIFIED"}

    return mock_stream


@pytest.fixture
def mock_run_process(monkeypatch: pytest.MonkeyPatch):
    mock = AsyncMock()
    monkeypatch.setattr(anyio, "run_process", mock)
    return mock


@pytest.fixture
def enable_store_api_key_in_secret(monkeypatch):
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_KUBERNETES_WORKER_CREATE_SECRET_FOR_API_KEY", "true"
    )


@pytest.fixture
def mock_api_key_secret_name_and_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_KUBERNETES_WORKER_API_KEY_SECRET_NAME", "test-secret"
    )
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_KUBERNETES_WORKER_API_KEY_SECRET_KEY", "value"
    )
    return "test-secret", "value"


from_template_and_values_cases = [
    (
        # default base template with no values
        KubernetesWorker.get_default_base_job_template(),
        {},
        KubernetesWorkerJobConfiguration(
            command=None,
            env={},
            labels={},
            name=None,
            namespace="default",
            job_manifest={
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "namespace": "default",
                    "generateName": "-",
                    "labels": {},
                },
                "spec": {
                    "backoffLimit": 0,
                    "template": {
                        "spec": {
                            "parallelism": 1,
                            "completions": 1,
                            "restartPolicy": "Never",
                            "containers": [
                                {
                                    "name": "prefect-job",
                                    "imagePullPolicy": "IfNotPresent",
                                }
                            ],
                        }
                    },
                },
            },
            cluster_config=None,
            job_watch_timeout_seconds=None,
            pod_watch_timeout_seconds=60,
            stream_output=True,
        ),
        lambda flow_run,
        deployment,
        flow,
        work_pool,
        worker_name: KubernetesWorkerJobConfiguration(
            command="prefect flow-run execute",
            env={
                **get_current_settings().to_environment_variables(exclude_unset=True),
                "PREFECT__FLOW_RUN_ID": str(flow_run.id),
                "PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR": "reschedule",
            },
            labels={
                "prefect.io/flow-run-id": str(flow_run.id),
                "prefect.io/flow-run-name": flow_run.name,
                "prefect.io/version": _slugify_label_value(
                    prefect.__version__.split("+")[0]
                ),
                "prefect.io/deployment-id": str(deployment.id),
                "prefect.io/deployment-name": deployment.name,
                "prefect.io/flow-id": str(flow.id),
                "prefect.io/flow-name": flow.name,
                "prefect.io/worker-name": worker_name,
                "prefect.io/work-pool-name": work_pool.name,
                "prefect.io/work-pool-id": str(work_pool.id),
            },
            name=flow_run.name,
            namespace="default",
            job_manifest={
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "namespace": "default",
                    "generateName": f"{flow_run.name}-",
                    "labels": {
                        "prefect.io/flow-run-id": str(flow_run.id),
                        "prefect.io/flow-run-name": flow_run.name,
                        "prefect.io/version": _slugify_label_value(
                            prefect.__version__.split("+")[0]
                        ),
                        "prefect.io/deployment-id": str(deployment.id),
                        "prefect.io/deployment-name": deployment.name,
                        "prefect.io/flow-id": str(flow.id),
                        "prefect.io/flow-name": flow.name,
                        "prefect.io/worker-name": worker_name,
                        "prefect.io/work-pool-name": work_pool.name,
                        "prefect.io/work-pool-id": str(work_pool.id),
                    },
                },
                "spec": {
                    "backoffLimit": 0,
                    "template": {
                        "spec": {
                            "parallelism": 1,
                            "completions": 1,
                            "restartPolicy": "Never",
                            "containers": [
                                {
                                    "name": "prefect-job",
                                    "imagePullPolicy": "IfNotPresent",
                                    "env": [
                                        *[
                                            {"name": k, "value": v}
                                            for k, v in get_current_settings()
                                            .to_environment_variables(
                                                exclude_unset=True
                                            )
                                            .items()
                                        ],
                                        {
                                            "name": "PREFECT__FLOW_RUN_ID",
                                            "value": str(flow_run.id),
                                        },
                                        {
                                            "name": "PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR",
                                            "value": "reschedule",
                                        },
                                    ],
                                    "image": get_prefect_image_name(),
                                    "args": [
                                        "prefect",
                                        "flow-run",
                                        "execute",
                                    ],
                                }
                            ],
                        }
                    },
                },
            },
            cluster_config=None,
            job_watch_timeout_seconds=None,
            pod_watch_timeout_seconds=60,
            stream_output=True,
        ),
    ),
    (
        # default base template with custom env
        {
            "job_configuration": {
                "command": "{{ command }}",
                "env": "{{ env }}",
                "labels": "{{ labels }}",
                "name": "{{ name }}",
                "namespace": "{{ namespace }}",
                "job_manifest": {
                    "apiVersion": "batch/v1",
                    "kind": "Job",
                    "metadata": {
                        "labels": "{{ labels }}",
                        "namespace": "{{ namespace }}",
                        "generateName": "{{ name }}-",
                    },
                    "spec": {
                        "backoffLimit": 0,
                        "ttlSecondsAfterFinished": "{{ finished_job_ttl }}",
                        "template": {
                            "spec": {
                                "parallelism": 1,
                                "completions": 1,
                                "restartPolicy": "Never",
                                "serviceAccountName": "{{ service_account_name }}",
                                "containers": [
                                    {
                                        "name": "prefect-job",
                                        "env": [
                                            {
                                                "name": "TEST_ENV",
                                                "valueFrom": {
                                                    "secretKeyRef": {
                                                        "name": "test-secret",
                                                        "key": "shhhhh",
                                                    }
                                                },
                                            },
                                        ],
                                        "image": "{{ image }}",
                                        "imagePullPolicy": "{{ image_pull_policy }}",
                                        "args": "{{ command }}",
                                    }
                                ],
                            }
                        },
                    },
                },
                "cluster_config": "{{ cluster_config }}",
                "job_watch_timeout_seconds": "{{ job_watch_timeout_seconds }}",
                "pod_watch_timeout_seconds": "{{ pod_watch_timeout_seconds }}",
                "stream_output": "{{ stream_output }}",
            },
            "variables": {
                "description": "Default variables for the Kubernetes worker.\n\nThe schema for this class is used to populate the `variables` section of the default\nbase job template.",
                "type": "object",
                "properties": {
                    "name": {
                        "title": "Name",
                        "description": "Name given to infrastructure created by a worker.",
                        "type": "string",
                    },
                    "env": {
                        "title": "Environment Variables",
                        "description": "Environment variables to set when starting a flow run.",
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                    "labels": {
                        "title": "Labels",
                        "description": "Labels applied to infrastructure created by a worker.",
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                    "command": {
                        "title": "Command",
                        "description": "The command to use when starting a flow run. In most cases, this should be left blank and the command will be automatically generated by the worker.",
                        "type": "string",
                    },
                    "namespace": {
                        "title": "Namespace",
                        "description": "The Kubernetes namespace to create jobs within.",
                        "default": "default",
                        "type": "string",
                    },
                    "image": {
                        "title": "Image",
                        "description": "The image reference of a container image to use for created jobs. If not set, the latest Prefect image will be used.",
                        "example": "docker.io/prefecthq/prefect:3-latest",
                        "type": "string",
                    },
                    "service_account_name": {
                        "title": "Service Account Name",
                        "description": "The Kubernetes service account to use for job creation.",
                        "type": "string",
                    },
                    "image_pull_policy": {
                        "title": "Image Pull Policy",
                        "description": "The Kubernetes image pull policy to use for job containers.",
                        "default": "IfNotPresent",
                        "enum": ["IfNotPresent", "Always", "Never"],
                        "type": "string",
                    },
                    "finished_job_ttl": {
                        "title": "Finished Job TTL",
                        "description": "The number of seconds to retain jobs after completion. If set, finished jobs will be cleaned up by Kubernetes after the given delay. If not set, jobs will be retained indefinitely.",
                        "type": "integer",
                    },
                    "job_watch_timeout_seconds": {
                        "title": "Job Watch Timeout Seconds",
                        "description": "Number of seconds to wait for each event emitted by a job before timing out. If not set, the worker will wait for each event indefinitely.",
                        "type": "integer",
                    },
                    "pod_watch_timeout_seconds": {
                        "title": "Pod Watch Timeout Seconds",
                        "description": "Number of seconds to watch for pod creation before timing out.",
                        "default": 60,
                        "type": "integer",
                    },
                    "stream_output": {
                        "title": "Stream Output",
                        "description": "If set, output will be streamed from the job to local standard output.",
                        "default": True,
                        "type": "boolean",
                    },
                    "cluster_config": {
                        "title": "Cluster Config",
                        "description": "The Kubernetes cluster config to use for job creation.",
                        "allOf": [{"$ref": "#/definitions/KubernetesClusterConfig"}],
                    },
                },
                "definitions": {
                    "KubernetesClusterConfig": {
                        "title": "KubernetesClusterConfig",
                        "description": "Stores configuration for interaction with Kubernetes clusters.\n\nSee `from_file` for creation.",
                        "type": "object",
                        "properties": {
                            "config": {
                                "title": "Config",
                                "description": "The entire contents of a kubectl config file.",
                                "type": "object",
                            },
                            "context_name": {
                                "title": "Context Name",
                                "description": "The name of the kubectl context to use.",
                                "type": "string",
                            },
                        },
                        "required": ["config", "context_name"],
                        "block_type_slug": "kubernetes-cluster-config",
                        "secret_fields": [],
                        "block_schema_references": {},
                    }
                },
            },
        },
        {},
        KubernetesWorkerJobConfiguration(
            command=None,
            env={},
            labels={},
            name=None,
            namespace="default",
            job_manifest={
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "namespace": "default",
                    "generateName": "-",
                    "labels": {},
                },
                "spec": {
                    "backoffLimit": 0,
                    "template": {
                        "spec": {
                            "parallelism": 1,
                            "completions": 1,
                            "restartPolicy": "Never",
                            "containers": [
                                {
                                    "name": "prefect-job",
                                    "imagePullPolicy": "IfNotPresent",
                                    "env": [
                                        {
                                            "name": "TEST_ENV",
                                            "valueFrom": {
                                                "secretKeyRef": {
                                                    "name": "test-secret",
                                                    "key": "shhhhh",
                                                }
                                            },
                                        },
                                    ],
                                }
                            ],
                        }
                    },
                },
            },
            cluster_config=None,
            job_watch_timeout_seconds=None,
            pod_watch_timeout_seconds=60,
            stream_output=True,
        ),
        lambda flow_run,
        deployment,
        flow,
        work_pool,
        worker_name: KubernetesWorkerJobConfiguration(
            command="prefect flow-run execute",
            env={
                **get_current_settings().to_environment_variables(exclude_unset=True),
                "PREFECT__FLOW_RUN_ID": str(flow_run.id),
                "PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR": "reschedule",
            },
            labels={
                "prefect.io/flow-run-id": str(flow_run.id),
                "prefect.io/flow-run-name": flow_run.name,
                "prefect.io/version": _slugify_label_value(
                    prefect.__version__.split("+")[0]
                ),
                "prefect.io/deployment-id": str(deployment.id),
                "prefect.io/deployment-name": deployment.name,
                "prefect.io/flow-id": str(flow.id),
                "prefect.io/flow-name": flow.name,
                "prefect.io/worker-name": worker_name,
                "prefect.io/work-pool-name": work_pool.name,
                "prefect.io/work-pool-id": str(work_pool.id),
            },
            name=flow_run.name,
            namespace="default",
            job_manifest={
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "namespace": "default",
                    "generateName": f"{flow_run.name}-",
                    "labels": {
                        "prefect.io/flow-run-id": str(flow_run.id),
                        "prefect.io/flow-run-name": flow_run.name,
                        "prefect.io/version": _slugify_label_value(
                            prefect.__version__.split("+")[0]
                        ),
                        "prefect.io/deployment-id": str(deployment.id),
                        "prefect.io/deployment-name": deployment.name,
                        "prefect.io/flow-id": str(flow.id),
                        "prefect.io/flow-name": flow.name,
                        "prefect.io/worker-name": worker_name,
                        "prefect.io/work-pool-name": work_pool.name,
                        "prefect.io/work-pool-id": str(work_pool.id),
                    },
                },
                "spec": {
                    "backoffLimit": 0,
                    "template": {
                        "spec": {
                            "parallelism": 1,
                            "completions": 1,
                            "restartPolicy": "Never",
                            "containers": [
                                {
                                    "name": "prefect-job",
                                    "imagePullPolicy": "IfNotPresent",
                                    "env": [
                                        *[
                                            {"name": k, "value": v}
                                            for k, v in get_current_settings()
                                            .to_environment_variables(
                                                exclude_unset=True
                                            )
                                            .items()
                                        ],
                                        {
                                            "name": "PREFECT__FLOW_RUN_ID",
                                            "value": str(flow_run.id),
                                        },
                                        {
                                            "name": "PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR",
                                            "value": "reschedule",
                                        },
                                        {
                                            "name": "TEST_ENV",
                                            "valueFrom": {
                                                "secretKeyRef": {
                                                    "name": "test-secret",
                                                    "key": "shhhhh",
                                                }
                                            },
                                        },
                                    ],
                                    "image": get_prefect_image_name(),
                                    "args": [
                                        "prefect",
                                        "flow-run",
                                        "execute",
                                    ],
                                }
                            ],
                        }
                    },
                },
            },
            cluster_config=None,
            job_watch_timeout_seconds=None,
            pod_watch_timeout_seconds=60,
            stream_output=True,
        ),
    ),
    (
        # default base template with values
        KubernetesWorker.get_default_base_job_template(),
        {
            "name": "test",
            "job_watch_timeout_seconds": 120,
            "pod_watch_timeout_seconds": 90,
            "stream_output": False,
            "env": {
                "TEST_ENV": "test",
            },
            "labels": {
                "TEST_LABEL": "test label",
            },
            "service_account_name": "test-service-account",
            "image_pull_policy": "Always",
            "command": "echo hello",
            "image": "test-image:latest",
            "finished_job_ttl": 60,
            "namespace": "test-namespace",
            "backoff_limit": 6,
        },
        KubernetesWorkerJobConfiguration(
            command="echo hello",
            env={
                "TEST_ENV": "test",
            },
            labels={
                "TEST_LABEL": "test label",
            },
            name="test",
            namespace="test-namespace",
            job_manifest={
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "labels": {"TEST_LABEL": "test label"},
                    "namespace": "test-namespace",
                    "generateName": "test-",
                },
                "spec": {
                    "backoffLimit": 6,
                    "ttlSecondsAfterFinished": 60,
                    "template": {
                        "spec": {
                            "parallelism": 1,
                            "completions": 1,
                            "restartPolicy": "Never",
                            "serviceAccountName": "test-service-account",
                            "containers": [
                                {
                                    "name": "prefect-job",
                                    "env": {
                                        "TEST_ENV": "test",
                                    },
                                    "image": "test-image:latest",
                                    "imagePullPolicy": "Always",
                                    "args": "echo hello",
                                }
                            ],
                        }
                    },
                },
            },
            cluster_config=None,
            job_watch_timeout_seconds=120,
            pod_watch_timeout_seconds=90,
            stream_output=False,
        ),
        lambda flow_run,
        deployment,
        flow,
        work_pool,
        worker_name: KubernetesWorkerJobConfiguration(
            command="echo hello",
            env={
                **get_current_settings().to_environment_variables(exclude_unset=True),
                "PREFECT__FLOW_RUN_ID": str(flow_run.id),
                "TEST_ENV": "test",
            },
            labels={
                "prefect.io/flow-run-id": str(flow_run.id),
                "prefect.io/flow-run-name": flow_run.name,
                "prefect.io/version": _slugify_label_value(
                    prefect.__version__.split("+")[0]
                ),
                "prefect.io/deployment-id": str(deployment.id),
                "prefect.io/deployment-name": deployment.name,
                "prefect.io/flow-id": str(flow.id),
                "prefect.io/flow-name": flow.name,
                "prefect.io/worker-name": worker_name,
                "prefect.io/work-pool-name": work_pool.name,
                "prefect.io/work-pool-id": str(work_pool.id),
                "TEST_LABEL": "test label",
            },
            name="test",
            namespace="test-namespace",
            job_manifest={
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "namespace": "test-namespace",
                    "generateName": "test-",
                    "labels": {
                        "prefect.io/flow-run-id": str(flow_run.id),
                        "prefect.io/flow-run-name": flow_run.name,
                        "prefect.io/version": _slugify_label_value(
                            prefect.__version__.split("+")[0]
                        ),
                        "prefect.io/deployment-id": str(deployment.id),
                        "prefect.io/deployment-name": deployment.name,
                        "prefect.io/flow-id": str(flow.id),
                        "prefect.io/flow-name": flow.name,
                        "prefect.io/worker-name": worker_name,
                        "prefect.io/work-pool-name": work_pool.name,
                        "prefect.io/work-pool-id": str(work_pool.id),
                        "test_label": "test-label",
                    },
                },
                "spec": {
                    "backoffLimit": 6,
                    "ttlSecondsAfterFinished": 60,
                    "template": {
                        "spec": {
                            "parallelism": 1,
                            "completions": 1,
                            "restartPolicy": "Never",
                            "serviceAccountName": "test-service-account",
                            "containers": [
                                {
                                    "name": "prefect-job",
                                    "imagePullPolicy": "Always",
                                    "env": [
                                        *[
                                            {"name": k, "value": v}
                                            for k, v in get_current_settings()
                                            .to_environment_variables(
                                                exclude_unset=True
                                            )
                                            .items()
                                        ],
                                        {
                                            "name": "PREFECT__FLOW_RUN_ID",
                                            "value": str(flow_run.id),
                                        },
                                        {
                                            "name": "TEST_ENV",
                                            "value": "test",
                                        },
                                    ],
                                    "image": "test-image:latest",
                                    "args": ["echo", "hello"],
                                }
                            ],
                        }
                    },
                },
            },
            cluster_config=None,
            job_watch_timeout_seconds=120,
            pod_watch_timeout_seconds=90,
            stream_output=False,
        ),
    ),
    # custom template with values
    (
        {
            "job_configuration": {
                "command": "{{ command }}",
                "env": "{{ env }}",
                "labels": "{{ labels }}",
                "name": "{{ name }}",
                "namespace": "{{ namespace }}",
                "job_manifest": {
                    "apiVersion": "batch/v1",
                    "kind": "Job",
                    "spec": {
                        "template": {
                            "spec": {
                                "parallelism": 1,
                                "completions": 1,
                                "restartPolicy": "Never",
                                "containers": [
                                    {
                                        "name": "prefect-job",
                                        "image": "{{ image }}",
                                        "imagePullPolicy": "{{ image_pull_policy }}",
                                        "args": "{{ command }}",
                                        "resources": {
                                            "requests": {"memory": "{{ memory }}Mi"},
                                            "limits": {"memory": "200Mi"},
                                        },
                                    }
                                ],
                            }
                        }
                    },
                },
                "cluster_config": "{{ cluster_config }}",
                "job_watch_timeout_seconds": "{{ job_watch_timeout_seconds }}",
                "pod_watch_timeout_seconds": "{{ pod_watch_timeout_seconds }}",
                "stream_output": "{{ stream_output }}",
            },
            "variables": {
                "type": "object",
                "properties": {
                    "name": {
                        "title": "Name",
                        "description": "Name given to infrastructure created by a worker.",
                        "type": "string",
                    },
                    "env": {
                        "title": "Environment Variables",
                        "description": "Environment variables to set when starting a flow run.",
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                    "labels": {
                        "title": "Labels",
                        "description": "Labels applied to infrastructure created by a worker.",
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                    "command": {
                        "title": "Command",
                        "description": "The command to use when starting a flow run. In most cases, this should be left blank and the command will be automatically generated by the worker.",
                        "type": "string",
                    },
                    "namespace": {
                        "title": "Namespace",
                        "description": "The Kubernetes namespace to create jobs within.",
                        "default": "default",
                        "type": "string",
                    },
                    "image": {
                        "title": "Image",
                        "description": "The image reference of a container image to use for created jobs. If not set, the latest Prefect image will be used.",
                        "example": "docker.io/prefecthq/prefect:3-latest",
                        "type": "string",
                    },
                    "image_pull_policy": {
                        "title": "Image Pull Policy",
                        "description": "The Kubernetes image pull policy to use for job containers.",
                        "default": "IfNotPresent",
                        "enum": ["IfNotPresent", "Always", "Never"],
                        "type": "string",
                    },
                    "job_watch_timeout_seconds": {
                        "title": "Job Watch Timeout Seconds",
                        "description": "Number of seconds to wait for each event emitted by a job before timing out. If not set, the worker will wait for each event indefinitely.",
                        "type": "integer",
                    },
                    "pod_watch_timeout_seconds": {
                        "title": "Pod Watch Timeout Seconds",
                        "description": "Number of seconds to watch for pod creation before timing out.",
                        "default": 60,
                        "type": "integer",
                    },
                    "stream_output": {
                        "title": "Stream Output",
                        "description": "If set, output will be streamed from the job to local standard output.",
                        "default": True,
                        "type": "boolean",
                    },
                    "cluster_config": {
                        "title": "Cluster Config",
                        "description": "The Kubernetes cluster config to use for job creation.",
                        "allOf": [{"$ref": "#/definitions/KubernetesClusterConfig"}],
                    },
                    "memory": {
                        "title": "Memory",
                        "description": "The amount of memory to use for each job in MiB",
                        "default": 100,
                        "type": "number",
                        "min": 0,
                        "max": 200,
                    },
                },
                "definitions": {
                    "KubernetesClusterConfig": {
                        "title": "KubernetesClusterConfig",
                        "description": "Stores configuration for interaction with Kubernetes clusters.\n\nSee `from_file` for creation.",
                        "type": "object",
                        "properties": {
                            "config": {
                                "title": "Config",
                                "description": "The entire contents of a kubectl config file.",
                                "type": "object",
                            },
                            "context_name": {
                                "title": "Context Name",
                                "description": "The name of the kubectl context to use.",
                                "type": "string",
                            },
                        },
                        "required": ["config", "context_name"],
                        "block_type_slug": "kubernetes-cluster-config",
                        "secret_fields": [],
                        "block_schema_references": {},
                    }
                },
            },
        },
        {
            "name": "test",
            "job_watch_timeout_seconds": 120,
            "pod_watch_timeout_seconds": 90,
            "env": {
                "TEST_ENV": "test",
            },
            "labels": {
                "TEST_LABEL": "test label",
            },
            "image_pull_policy": "Always",
            "command": "echo hello",
            "image": "test-image:latest",
        },
        KubernetesWorkerJobConfiguration(
            command="echo hello",
            env={
                "TEST_ENV": "test",
            },
            labels={
                "TEST_LABEL": "test label",
            },
            name="test",
            namespace="default",
            job_manifest={
                "apiVersion": "batch/v1",
                "kind": "Job",
                "spec": {
                    "template": {
                        "spec": {
                            "parallelism": 1,
                            "completions": 1,
                            "restartPolicy": "Never",
                            "containers": [
                                {
                                    "name": "prefect-job",
                                    "image": "test-image:latest",
                                    "imagePullPolicy": "Always",
                                    "args": "echo hello",
                                    "resources": {
                                        "limits": {
                                            "memory": "200Mi",
                                        },
                                        "requests": {
                                            "memory": "100Mi",
                                        },
                                    },
                                },
                            ],
                        }
                    }
                },
            },
            cluster_config=None,
            job_watch_timeout_seconds=120,
            pod_watch_timeout_seconds=90,
            stream_output=True,
        ),
        lambda flow_run,
        deployment,
        flow,
        work_pool,
        worker_name: KubernetesWorkerJobConfiguration(
            command="echo hello",
            env={
                **get_current_settings().to_environment_variables(exclude_unset=True),
                "PREFECT__FLOW_RUN_ID": str(flow_run.id),
                "TEST_ENV": "test",
            },
            labels={
                "prefect.io/flow-run-id": str(flow_run.id),
                "prefect.io/flow-run-name": flow_run.name,
                "prefect.io/version": prefect.__version__.split("+")[0],
                "prefect.io/deployment-id": str(deployment.id),
                "prefect.io/deployment-name": deployment.name,
                "prefect.io/flow-id": str(flow.id),
                "prefect.io/flow-name": flow.name,
                "prefect.io/worker-name": worker_name,
                "prefect.io/work-pool-name": work_pool.name,
                "prefect.io/work-pool-id": str(work_pool.id),
                "TEST_LABEL": "test label",
            },
            name="test",
            namespace="default",
            job_manifest={
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "namespace": "default",
                    "generateName": "test-",
                    "labels": {
                        "prefect.io/flow-run-id": str(flow_run.id),
                        "prefect.io/flow-run-name": flow_run.name,
                        "prefect.io/version": _slugify_label_value(
                            prefect.__version__.split("+")[0]
                        ),
                        "prefect.io/deployment-id": str(deployment.id),
                        "prefect.io/deployment-name": deployment.name,
                        "prefect.io/flow-id": str(flow.id),
                        "prefect.io/flow-name": flow.name,
                        "prefect.io/worker-name": worker_name,
                        "prefect.io/work-pool-name": work_pool.name,
                        "prefect.io/work-pool-id": str(work_pool.id),
                        "test_label": "test-label",
                    },
                },
                "spec": {
                    "template": {
                        "spec": {
                            "parallelism": 1,
                            "completions": 1,
                            "restartPolicy": "Never",
                            "containers": [
                                {
                                    "name": "prefect-job",
                                    "imagePullPolicy": "Always",
                                    "env": [
                                        *[
                                            {"name": k, "value": v}
                                            for k, v in get_current_settings()
                                            .to_environment_variables(
                                                exclude_unset=True
                                            )
                                            .items()
                                        ],
                                        {
                                            "name": "PREFECT__FLOW_RUN_ID",
                                            "value": str(flow_run.id),
                                        },
                                        {
                                            "name": "TEST_ENV",
                                            "value": "test",
                                        },
                                    ],
                                    "image": "test-image:latest",
                                    "args": ["echo", "hello"],
                                    "resources": {
                                        "limits": {
                                            "memory": "200Mi",
                                        },
                                        "requests": {
                                            "memory": "100Mi",
                                        },
                                    },
                                }
                            ],
                        }
                    }
                },
            },
            cluster_config=None,
            job_watch_timeout_seconds=120,
            pod_watch_timeout_seconds=90,
            stream_output=True,
        ),
    ),
]


class TestKubernetesWorkerJobConfiguration:
    @pytest.fixture
    def flow_run(self):
        return FlowRun(flow_id=uuid.uuid4(), name="my-flow-run-name")

    @pytest.fixture
    def deployment(self):
        return DeploymentResponse(name="my-deployment-name", flow_id=uuid.uuid4())

    @pytest.fixture
    def work_pool(self):
        return WorkPool(name="my-work-pool-name", type="kubernetes")

    @pytest.fixture
    def flow(self):
        return Flow(name="my-flow-name")

    @pytest.mark.parametrize(
        "template,values,expected_after_template,expected_after_preparation",
        from_template_and_values_cases,
        ids=[
            "default base template with no values",
            "default base template with custom env",
            "default base template with values",
            "custom template with values",
        ],
    )
    async def test_job_configuration_preparation(
        self,
        template,
        values,
        expected_after_template,
        expected_after_preparation,
        flow_run,
        deployment,
        flow,
        work_pool,
    ):
        """Tests that the job configuration is correctly templated and prepared."""
        result = await KubernetesWorkerJobConfiguration.from_template_and_values(
            base_job_template=template,
            values=values,
        )
        # comparing dictionaries produces cleaner diffs
        assert result.model_dump() == expected_after_template.model_dump()

        result.prepare_for_flow_run(
            flow_run=flow_run,
            deployment=deployment,
            flow=flow,
            work_pool=work_pool,
            worker_name="test-worker",
        )

        assert (
            result.model_dump()
            == expected_after_preparation(
                flow_run=flow_run,
                deployment=deployment,
                flow=flow,
                work_pool=work_pool,
                worker_name="test-worker",
            ).model_dump()
        )

    async def test_validates_against_an_empty_job(self):
        """We should give a human-friendly error when the user provides an empty custom
        Job manifest"""

        template = KubernetesWorker.get_default_base_job_template()
        template["job_configuration"]["job_manifest"] = {}
        with pytest.raises(ValidationError) as excinfo:
            await KubernetesWorkerJobConfiguration.from_template_and_values(
                template, {}
            )

        assert len(errs := excinfo.value.errors()) == 1
        assert "Job is missing required attributes" in errs[0]["msg"]
        assert "/apiVersion" in errs[0]["msg"]
        assert "/kind" in errs[0]["msg"]
        assert "/spec" in errs[0]["msg"]

    async def test_validates_for_a_job_missing_deeper_attributes(self):
        """We should give a human-friendly error when the user provides an incomplete
        custom Job manifest"""
        template = KubernetesWorker.get_default_base_job_template()
        template["job_configuration"]["job_manifest"] = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {},
            "spec": {"template": {"spec": {}}},
        }

        with pytest.raises(ValidationError) as excinfo:
            await KubernetesWorkerJobConfiguration.from_template_and_values(
                template, {}
            )

        assert len(errs := excinfo.value.errors()) == 1
        assert "Job is missing required attributes" in errs[0]["msg"]
        assert "/spec/template/spec/completions" in errs[0]["msg"]
        assert "/spec/template/spec/containers" in errs[0]["msg"]
        assert "/spec/template/spec/parallelism" in errs[0]["msg"]
        assert "/spec/template/spec/restartPolicy" in errs[0]["msg"]

    async def test_validates_for_a_job_with_incompatible_values(self):
        """We should give a human-friendly error when the user provides a custom Job
        manifest that is attempting to change required values."""
        template = KubernetesWorker.get_default_base_job_template()
        template["job_configuration"]["job_manifest"] = {
            "apiVersion": "v1",
            "kind": "JobbledyJunk",
            "metadata": {"labels": {}},
            "spec": {
                "template": {
                    "spec": {
                        "parallelism": 1,
                        "completions": 1,
                        "restartPolicy": "Never",
                        "containers": [
                            {
                                "name": "prefect-job",
                                "env": [],
                            }
                        ],
                    }
                }
            },
        }

        with pytest.raises(ValidationError) as excinfo:
            await KubernetesWorkerJobConfiguration.from_template_and_values(
                template, {}
            )

        assert len(errs := excinfo.value.errors()) == 1
        assert "Job has incompatible values" in errs[0]["msg"]
        assert "/apiVersion must have value 'batch/v1'" in errs[0]["msg"]
        assert "/kind must have value 'Job'" in errs[0]["msg"]

    async def test_user_supplied_base_job_with_labels(self, flow_run):
        """The user can supply a custom base job with labels and they will be
        included in the final manifest"""
        template = KubernetesWorker.get_default_base_job_template()
        template["job_configuration"]["job_manifest"] = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"labels": {"my-custom-label": "sweet"}},
            "spec": {
                "template": {
                    "spec": {
                        "parallelism": 1,
                        "completions": 1,
                        "restartPolicy": "Never",
                        "containers": [
                            {
                                "name": "prefect-job",
                                "env": [],
                            }
                        ],
                    }
                }
            },
        }

        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            template, {}
        )
        assert configuration.job_manifest["metadata"]["labels"] == {
            # the labels provided in the user's job base
            "my-custom-label": "sweet",
        }
        configuration.prepare_for_flow_run(flow_run)
        assert (
            configuration.job_manifest["metadata"]["labels"]["my-custom-label"]
            == "sweet"
        )

    async def test_user_can_supply_a_sidecar_container_and_volume(self, flow_run):
        """The user can supply a custom base job that includes more complex
        modifications, like a sidecar container and volumes"""
        template = KubernetesWorker.get_default_base_job_template()
        template["job_configuration"]["job_manifest"] = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"labels": {}},
            "spec": {
                "template": {
                    "spec": {
                        "parallelism": 1,
                        "completions": 1,
                        "restartPolicy": "Never",
                        "containers": [
                            {
                                "name": "prefect-job",
                                "env": [],
                            },
                            {
                                "name": "my-sidecar",
                                "image": "cool-peeps/cool-code:latest",
                                "volumeMounts": [
                                    {"name": "data-volume", "mountPath": "/data/"}
                                ],
                            },
                        ],
                        "volumes": [
                            {"name": "data-volume", "hostPath": "/all/the/data/"}
                        ],
                    }
                }
            },
        }

        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            template, {}
        )
        configuration.prepare_for_flow_run(flow_run)

        pod = configuration.job_manifest["spec"]["template"]["spec"]

        assert pod["volumes"] == [{"name": "data-volume", "hostPath": "/all/the/data/"}]

        # the prefect-job container is still populated
        assert pod["containers"][0]["name"] == "prefect-job"
        assert pod["containers"][0]["args"] == ["prefect", "flow-run", "execute"]

        assert pod["containers"][1] == {
            "name": "my-sidecar",
            "image": "cool-peeps/cool-code:latest",
            "volumeMounts": [{"name": "data-volume", "mountPath": "/data/"}],
        }

    def test_env_can_be_a_list(self):
        job_manifest = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"labels": {"my-custom-label": "sweet"}},
            "spec": {
                "template": {
                    "spec": {
                        "parallelism": 1,
                        "completions": 1,
                        "restartPolicy": "Never",
                        "containers": [
                            {
                                "name": "prefect-job",
                                "env": [],
                            }
                        ],
                    }
                }
            },
        }
        KubernetesWorkerJobConfiguration(
            job_manifest=job_manifest,
            env=[
                {
                    "name": "TEST_ENV",
                    "value": "test",
                }
            ],
        )


class TestKubernetesWorker:
    @pytest.fixture
    async def default_configuration(self):
        return await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(), {}
        )

    @pytest.fixture
    def flow_run(self):
        return FlowRun(flow_id=uuid.uuid4(), name="my-flow-run-name")

    async def test_creates_job_by_building_a_manifest(
        self,
        default_configuration: KubernetesWorkerJobConfiguration,
        flow_run,
        mock_batch_client,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_completed_pod,
    ):
        default_configuration.prepare_for_flow_run(flow_run)
        expected_manifest = default_configuration.job_manifest
        mock_watch.return_value.stream = mock.Mock(
            side_effect=mock_pods_stream_that_returns_completed_pod
        )
        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run=flow_run, configuration=default_configuration)
            mock_core_client.return_value.list_namespaced_pod.assert_called_with(
                namespace=default_configuration.namespace,
                label_selector="job-name=mock-job",
            )

            mock_batch_client.return_value.create_namespaced_job.assert_called_with(
                "default",
                expected_manifest,
            )

    async def test_task_status_receives_job_pid(
        self,
        default_configuration: KubernetesWorkerJobConfiguration,
        flow_run,
        mock_batch_client,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_completed_pod,
    ):
        mock_watch.return_value.stream = mock.Mock(
            side_effect=mock_pods_stream_that_returns_completed_pod
        )
        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            fake_status = MagicMock(spec=anyio.abc.TaskStatus)
            await k8s_worker.run(
                flow_run=flow_run,
                configuration=default_configuration,
                task_status=fake_status,
            )
            expected_value = f"{MOCK_CLUSTER_UID}:mock-namespace:mock-job"
            fake_status.started.assert_called_once_with(expected_value)

    async def test_cluster_uid_uses_env_var_if_set(
        self,
        default_configuration: KubernetesWorkerJobConfiguration,
        flow_run,
        mock_batch_client,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_completed_pod,
        monkeypatch,
    ):
        mock_watch.return_value.stream = mock.Mock(
            side_effect=mock_pods_stream_that_returns_completed_pod
        )
        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            monkeypatch.setenv("PREFECT_KUBERNETES_CLUSTER_UID", "test-uid")
            fake_status = MagicMock(spec=anyio.abc.TaskStatus)
            result = await k8s_worker.run(
                flow_run=flow_run,
                configuration=default_configuration,
                task_status=fake_status,
            )

            mock_core_client.read_namespace.assert_not_called()
            expected_value = "test-uid:mock-namespace:mock-job"
            assert result.identifier == expected_value
            fake_status.started.assert_called_once_with(expected_value)

    async def test_task_group_start_returns_job_pid(
        self,
        flow_run,
        default_configuration: KubernetesWorkerJobConfiguration,
        mock_batch_client,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_completed_pod,
    ):
        mock_watch.return_value.stream = mock.Mock(
            side_effect=mock_pods_stream_that_returns_completed_pod
        )
        expected_value = f"{MOCK_CLUSTER_UID}:mock-namespace:mock-job"
        async with anyio.create_task_group() as tg:
            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                result = await tg.start(k8s_worker.run, flow_run, default_configuration)
                assert result == expected_value

    async def test_missing_job_returns_bad_status_code(
        self,
        flow_run,
        default_configuration: KubernetesWorkerJobConfiguration,
        mock_batch_client,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_completed_pod,
        caplog,
    ):
        mock_batch_client.return_value.read_namespaced_job.side_effect = ApiException(
            status=404, reason="Job not found"
        )
        mock_watch.return_value.stream = mock.Mock(
            side_effect=mock_pods_stream_that_returns_completed_pod
        )

        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            result = await k8s_worker.run(
                flow_run=flow_run, configuration=default_configuration
            )

            _, _, job_name = k8s_worker._parse_infrastructure_pid(result.identifier)

            assert result.status_code == -1
            assert f"Job {job_name!r} was removed" in caplog.text

    @pytest.mark.parametrize(
        "job_name,clean_name",
        [
            ("infra-run", "infra-run-"),
            ("infra-run-", "infra-run-"),
            ("_infra_run", "infra-run-"),
            ("...infra_run", "infra-run-"),
            ("._-infra_run", "infra-run-"),
            ("9infra-run", "9infra-run-"),
            ("-infra.run", "infra-run-"),
            ("infra*run", "infra-run-"),
            ("infra9.-foo_bar^x", "infra9-foo-bar-x-"),
        ],
    )
    async def test_job_name_creates_valid_name(
        self,
        default_configuration: KubernetesWorkerJobConfiguration,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_completed_pod,
        mock_batch_client,
        job_name,
        clean_name,
    ):
        default_configuration.name = job_name
        default_configuration.prepare_for_flow_run(flow_run)
        mock_watch.return_value.stream = mock.Mock(
            side_effect=mock_pods_stream_that_returns_completed_pod
        )
        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run=flow_run, configuration=default_configuration)
            mock_batch_client.return_value.create_namespaced_job.assert_called_once()
            call_name = mock_batch_client.return_value.create_namespaced_job.call_args[
                0
            ][1]["metadata"]["generateName"]
            assert call_name == clean_name

    async def test_uses_image_variable(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_completed_pod,
        mock_batch_client,
    ):
        mock_watch.return_value.stream = mock.Mock(
            side_effect=mock_pods_stream_that_returns_completed_pod
        )
        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(), {"image": "foo"}
        )
        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run, configuration)
            mock_batch_client.return_value.create_namespaced_job.assert_called_once()
            image = mock_batch_client.return_value.create_namespaced_job.call_args[0][
                1
            ]["spec"]["template"]["spec"]["containers"][0]["image"]
            assert image == "foo"

    async def test_can_store_api_key_in_secret(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_completed_pod,
        mock_batch_client,
        enable_store_api_key_in_secret,
    ):
        mock_watch.return_value.stream = mock.Mock(
            side_effect=mock_pods_stream_that_returns_completed_pod
        )
        mock_core_client.return_value.read_namespaced_secret.side_effect = ApiException(
            status=404
        )

        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(), {"image": "foo"}
        )
        with temporary_settings(updates={PREFECT_API_KEY: "fake"}):
            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                configuration.prepare_for_flow_run(flow_run=flow_run)
                await k8s_worker.run(flow_run, configuration)
                mock_batch_client.return_value.create_namespaced_job.assert_called_once()
                env = mock_batch_client.return_value.create_namespaced_job.call_args[0][
                    1
                ]["spec"]["template"]["spec"]["containers"][0]["env"]
                assert {
                    "name": "PREFECT_API_KEY",
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": f"prefect-{_slugify_name(k8s_worker.name)}-api-key",
                            "key": "value",
                        }
                    },
                } in env
                mock_core_client.return_value.create_namespaced_secret.assert_called_with(
                    namespace=configuration.namespace,
                    body=V1Secret(
                        api_version="v1",
                        kind="Secret",
                        metadata=V1ObjectMeta(
                            name=f"prefect-{_slugify_name(k8s_worker.name)}-api-key",
                            namespace=configuration.namespace,
                        ),
                        data={
                            "value": base64.b64encode("fake".encode("utf-8")).decode(
                                "utf-8"
                            )
                        },
                    ),
                )

        # Make sure secret gets deleted
        assert await mock_core_client.return_value.delete_namespaced_secret(
            name=f"prefect-{_slugify_name(k8s_worker.name)}-api-key",
            namespace=configuration.namespace,
        )

    async def test_store_api_key_in_existing_secret(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_running_pod,
        mock_batch_client,
        enable_store_api_key_in_secret,
    ):
        mock_watch.return_value.stream = mock_pods_stream_that_returns_running_pod

        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(), {"image": "foo"}
        )
        with temporary_settings(updates={PREFECT_API_KEY: "fake"}):
            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                mock_core_client.return_value.read_namespaced_secret.return_value = (
                    V1Secret(
                        api_version="v1",
                        kind="Secret",
                        metadata=V1ObjectMeta(
                            name=f"prefect-{_slugify_name(k8s_worker.name)}-api-key",
                            namespace=configuration.namespace,
                        ),
                        data={
                            "value": base64.b64encode("fake".encode("utf-8")).decode(
                                "utf-8"
                            )
                        },
                    )
                )

                configuration.prepare_for_flow_run(flow_run=flow_run)
                await k8s_worker.run(flow_run, configuration)
                mock_batch_client.return_value.create_namespaced_job.assert_called_once()
                env = mock_batch_client.return_value.create_namespaced_job.call_args[0][
                    1
                ]["spec"]["template"]["spec"]["containers"][0]["env"]
                assert {
                    "name": "PREFECT_API_KEY",
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": f"prefect-{_slugify_name(k8s_worker.name)}-api-key",
                            "key": "value",
                        }
                    },
                } in env
                mock_core_client.return_value.replace_namespaced_secret.assert_called_with(
                    name=f"prefect-{_slugify_name(k8s_worker.name)}-api-key",
                    namespace=configuration.namespace,
                    body=V1Secret(
                        api_version="v1",
                        kind="Secret",
                        metadata=V1ObjectMeta(
                            name=f"prefect-{_slugify_name(k8s_worker.name)}-api-key",
                            namespace=configuration.namespace,
                        ),
                        data={
                            "value": base64.b64encode("fake".encode("utf-8")).decode(
                                "utf-8"
                            )
                        },
                    ),
                )

    async def test_use_existing_secret_name(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_running_pod,
        mock_batch_client,
        mock_api_key_secret_name_and_key: tuple[str, str],
    ):
        mock_api_key_secret_name, mock_api_key_secret_key = (
            mock_api_key_secret_name_and_key
        )
        mock_watch.return_value.stream = mock_pods_stream_that_returns_running_pod

        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(), {"image": "foo"}
        )
        with temporary_settings(updates={PREFECT_API_KEY: "fake"}):
            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                mock_core_client.return_value.read_namespaced_secret.return_value = (
                    V1Secret(
                        api_version="v1",
                        kind="Secret",
                        metadata=V1ObjectMeta(
                            name=f"prefect-{_slugify_name(k8s_worker.name)}-api-key",
                            namespace=configuration.namespace,
                        ),
                        data={
                            "value": base64.b64encode("fake".encode("utf-8")).decode(
                                "utf-8"
                            )
                        },
                    )
                )

                configuration.prepare_for_flow_run(flow_run=flow_run)
                await k8s_worker.run(flow_run, configuration)
                mock_batch_client.return_value.create_namespaced_job.assert_called_once()
                env = mock_batch_client.return_value.create_namespaced_job.call_args[0][
                    1
                ]["spec"]["template"]["spec"]["containers"][0]["env"]
                assert {
                    "name": "PREFECT_API_KEY",
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": mock_api_key_secret_name,
                            "key": mock_api_key_secret_key,
                        }
                    },
                } in env

    async def test_existing_secret_name_takes_precedence(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_running_pod,
        mock_batch_client,
        mock_api_key_secret_name_and_key: tuple[str, str],
        enable_store_api_key_in_secret,
    ):
        mock_api_key_secret_name, mock_api_key_secret_key = (
            mock_api_key_secret_name_and_key
        )
        mock_watch.return_value.stream = mock_pods_stream_that_returns_running_pod

        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(), {"image": "foo"}
        )
        with temporary_settings(updates={PREFECT_API_KEY: "fake"}):
            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                mock_core_client.return_value.read_namespaced_secret.return_value = (
                    V1Secret(
                        api_version="v1",
                        kind="Secret",
                        metadata=V1ObjectMeta(
                            name=f"prefect-{_slugify_name(k8s_worker.name)}-api-key",
                            namespace=configuration.namespace,
                        ),
                        data={
                            "value": base64.b64encode("fake".encode("utf-8")).decode(
                                "utf-8"
                            )
                        },
                    )
                )

                configuration.prepare_for_flow_run(flow_run=flow_run)
                await k8s_worker.run(flow_run, configuration)
                mock_batch_client.return_value.create_namespaced_job.assert_called_once()
                env = mock_batch_client.return_value.create_namespaced_job.call_args[0][
                    1
                ]["spec"]["template"]["spec"]["containers"][0]["env"]
                assert {
                    "name": "PREFECT_API_KEY",
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": mock_api_key_secret_name,
                            "key": mock_api_key_secret_key,
                        }
                    },
                } in env
                mock_core_client.return_value.replace_namespaced_secret.assert_not_called()

    async def test_create_job_failure(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_batch_client,
    ):
        response = MagicMock()
        response.data = json.dumps(
            {
                "kind": "Status",
                "apiVersion": "v1",
                "metadata": {},
                "status": "Failure",
                "message": 'jobs.batch is forbidden: User "system:serviceaccount:helm-test:prefect-worker-dev" cannot create resource "jobs" in API group "batch" in the namespace "prefect"',
                "reason": "Forbidden",
                "details": {"group": "batch", "kind": "jobs"},
                "code": 403,
            }
        )
        response.status = 403
        response.reason = "Forbidden"

        mock_batch_client.return_value.create_namespaced_job.side_effect = ApiException(
            http_resp=response
        )

        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(), {"image": "foo"}
        )
        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            with pytest.raises(
                InfrastructureError,
                match=re.escape(
                    "Unable to create Kubernetes job: Forbidden: jobs.batch is forbidden: User "
                    '"system:serviceaccount:helm-test:prefect-worker-dev" cannot '
                    'create resource "jobs" in API group "batch" in the namespace '
                    '"prefect"'
                ),
            ):
                await k8s_worker.run(flow_run, configuration)

    async def test_create_job_retries(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_batch_client,
    ):
        MAX_ATTEMPTS = 3
        response = MagicMock()
        response.data = json.dumps(
            {
                "kind": "Status",
                "apiVersion": "v1",
                "metadata": {},
                "status": "Failure",
                "message": 'jobs.batch is forbidden: User "system:serviceaccount:helm-test:prefect-worker-dev" cannot create resource "jobs" in API group "batch" in the namespace "prefect"',
                "reason": "Forbidden",
                "details": {"group": "batch", "kind": "jobs"},
                "code": 403,
            }
        )
        response.status = 403
        response.reason = "Forbidden"

        mock_batch_client.return_value.create_namespaced_job.side_effect = ApiException(
            http_resp=response
        )

        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(), {"image": "foo"}
        )
        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            with pytest.raises(
                InfrastructureError,
                match=re.escape(
                    "Unable to create Kubernetes job: Forbidden: jobs.batch is forbidden: User "
                    '"system:serviceaccount:helm-test:prefect-worker-dev" cannot '
                    'create resource "jobs" in API group "batch" in the namespace '
                    '"prefect"'
                ),
            ):
                await k8s_worker.run(flow_run, configuration)

        assert (
            mock_batch_client.return_value.create_namespaced_job.call_count
            == MAX_ATTEMPTS
        )

    async def test_create_job_failure_no_reason(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_batch_client,
    ):
        response = MagicMock()
        response.data = json.dumps(
            {
                "kind": "Status",
                "apiVersion": "v1",
                "metadata": {},
                "status": "Failure",
                "message": 'jobs.batch is forbidden: User "system:serviceaccount:helm-test:prefect-worker-dev" cannot create resource "jobs" in API group "batch" in the namespace "prefect"',
                "reason": "Forbidden",
                "details": {"group": "batch", "kind": "jobs"},
                "code": 403,
            }
        )
        response.status = 403
        response.reason = None

        mock_batch_client.return_value.create_namespaced_job.side_effect = ApiException(
            http_resp=response
        )

        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(), {"image": "foo"}
        )
        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            with pytest.raises(
                InfrastructureError,
                match=re.escape(
                    "Unable to create Kubernetes job: jobs.batch is forbidden: User "
                    '"system:serviceaccount:helm-test:prefect-worker-dev" cannot '
                    'create resource "jobs" in API group "batch" in the namespace '
                    '"prefect"'
                ),
            ):
                await k8s_worker.run(flow_run, configuration)

    async def test_create_job_failure_no_message(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_batch_client,
    ):
        response = MagicMock()
        response.data = json.dumps(
            {
                "kind": "Status",
                "apiVersion": "v1",
                "metadata": {},
                "status": "Failure",
                "reason": "Forbidden",
                "details": {"group": "batch", "kind": "jobs"},
                "code": 403,
            }
        )
        response.status = 403
        response.reason = "Test"

        mock_batch_client.return_value.create_namespaced_job.side_effect = ApiException(
            http_resp=response
        )

        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(), {"image": "foo"}
        )
        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            with pytest.raises(
                InfrastructureError,
                match=re.escape("Unable to create Kubernetes job: Test"),
            ):
                await k8s_worker.run(flow_run, configuration)

    async def test_create_job_failure_no_response_body(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_batch_client,
    ):
        response = MagicMock()
        response.data = None
        response.status = 403
        response.reason = "Test"

        mock_batch_client.return_value.create_namespaced_job.side_effect = ApiException(
            http_resp=response
        )

        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(), {"image": "foo"}
        )
        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            with pytest.raises(
                InfrastructureError,
                match=re.escape("Unable to create Kubernetes job: Test"),
            ):
                await k8s_worker.run(flow_run, configuration)

    async def test_allows_image_setting_from_manifest(
        self,
        default_configuration: KubernetesWorkerJobConfiguration,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_running_pod,
        mock_batch_client,
    ):
        mock_watch.return_value.stream = mock_pods_stream_that_returns_running_pod

        default_configuration.job_manifest["spec"]["template"]["spec"]["containers"][0][
            "image"
        ] = "test"
        default_configuration.prepare_for_flow_run(flow_run)

        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run, default_configuration)
            mock_batch_client.return_value.create_namespaced_job.assert_called_once()
            image = mock_batch_client.return_value.create_namespaced_job.call_args[0][
                1
            ]["spec"]["template"]["spec"]["containers"][0]["image"]
            assert image == "test"

    async def test_uses_labels_setting(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_running_pod,
        mock_batch_client,
    ):
        mock_watch.return_value.stream = mock_pods_stream_that_returns_running_pod
        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(),
            {"labels": {"foo": "foo", "bar": "bar"}},
        )

        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run, configuration)
            mock_batch_client.return_value.create_namespaced_job.assert_called_once()
            labels = mock_batch_client.return_value.create_namespaced_job.call_args[0][
                1
            ]["metadata"]["labels"]
            assert labels["foo"] == "foo"
            assert labels["bar"] == "bar"

    async def test_sets_environment_variables(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_running_pod,
        mock_batch_client,
    ):
        mock_watch.return_value.stream = mock_pods_stream_that_returns_running_pod
        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(),
            {"env": {"foo": "FOO", "bar": "BAR"}},
        )
        configuration.prepare_for_flow_run(flow_run)

        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run, configuration)
            mock_batch_client.return_value.create_namespaced_job.assert_called_once()

            manifest = mock_batch_client.return_value.create_namespaced_job.call_args[
                0
            ][1]
            pod = manifest["spec"]["template"]["spec"]
            env = pod["containers"][0]["env"]
            assert env == [
                {"name": key, "value": value}
                for key, value in {
                    **configuration._base_environment(),
                    **configuration._base_flow_run_environment(flow_run),
                    "foo": "FOO",
                    "bar": "BAR",
                    "PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR": "reschedule",
                }.items()
            ]

    async def test_uses_custom_env_list_from_base_template(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_running_pod,
        mock_batch_client,
    ):
        mock_watch.return_value.stream = mock_pods_stream_that_returns_running_pod

        # Create a custom base job template with list-style env
        custom_base_template = KubernetesWorker.get_default_base_job_template()
        custom_base_template["job_configuration"]["job_manifest"]["spec"]["template"][
            "spec"
        ]["containers"][0]["env"] = [
            {"name": "MYENV", "value": "foobarbaz"},
            {
                "name": "MYENVFROM",
                "valueFrom": {"secretKeyRef": {"name": "something", "key": "SECRET"}},
            },
        ]

        # Create a KubernetesWorkerJobConfiguration using the custom template
        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            custom_base_template,
            {},
        )
        configuration.prepare_for_flow_run(flow_run)

        # Run the worker with this configuration
        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run, configuration)

        mock_batch_client.return_value.create_namespaced_job.assert_called_once()
        created_job = mock_batch_client.return_value.create_namespaced_job.call_args[0][
            1
        ]
        created_env = created_job["spec"]["template"]["spec"]["containers"][0]["env"]

        # Check if the custom environment variables are present
        assert any(
            env
            for env in created_env
            if env["name"] == "MYENV" and env["value"] == "foobarbaz"
        )
        assert any(
            env
            for env in created_env
            if env["name"] == "MYENVFROM"
            and env["valueFrom"]["secretKeyRef"]["name"] == "something"
            and env["valueFrom"]["secretKeyRef"]["key"] == "SECRET"
        )

        assert any(env for env in created_env if env["name"] == "PREFECT__FLOW_RUN_ID")

    async def test_allows_unsetting_environment_variables(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_running_pod,
        mock_batch_client,
    ):
        mock_watch.return_value.stream = mock_pods_stream_that_returns_running_pod
        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(),
            {"env": {"PREFECT_TEST_MODE": None}},
        )
        configuration.prepare_for_flow_run(flow_run)
        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run, configuration)
            mock_batch_client.return_value.create_namespaced_job.assert_called_once()

            manifest = mock_batch_client.return_value.create_namespaced_job.call_args[
                0
            ][1]
            pod = manifest["spec"]["template"]["spec"]
            env = pod["containers"][0]["env"]
            env_names = {variable["name"] for variable in env}
            assert "PREFECT_TEST_MODE" not in env_names

    @pytest.mark.parametrize(
        "given,expected",
        [
            ("a-valid-dns-subdomain1/and-a-name", "a-valid-dns-subdomain1/and-a-name"),
            (
                "a-prefix-with-invalid$@*^$@-characters/and-a-name",
                "a-prefix-with-invalid-characters/and-a-name",
            ),
            (
                "a-name-with-invalid$@*^$@-characters",
                "a-name-with-invalid-characters",
            ),
            ("/a-name-that-starts-with-slash", "a-name-that-starts-with-slash"),
            ("a-prefix/and-a-name/-with-a-slash", "a-prefix/and-a-name-with-a-slash"),
            (
                "_a-name-that-starts-with-underscore",
                "a-name-that-starts-with-underscore",
            ),
            ("-a-name-that-starts-with-dash", "a-name-that-starts-with-dash"),
            (".a-name-that-starts-with-period", "a-name-that-starts-with-period"),
            ("a-name-that-ends-with-underscore_", "a-name-that-ends-with-underscore"),
            ("a-name-that-ends-with-dash-", "a-name-that-ends-with-dash"),
            ("a-name-that-ends-with-period.", "a-name-that-ends-with-period"),
            (
                "._.-a-name-with-trailing-leading-chars-__-.",
                "a-name-with-trailing-leading-chars",
            ),
            ("a-prefix/and-a-name/-with-a-slash", "a-prefix/and-a-name-with-a-slash"),
            # Truncation of the prefix
            ("a" * 300 + "/and-a-name", "a" * 253 + "/and-a-name"),
            # Truncation of the name
            ("a" * 300, "a" * 63),
            # Truncation of the prefix and name together
            ("a" * 300 + "/" + "b" * 100, "a" * 253 + "/" + "b" * 63),
            # All invalid passes through
            ("$@*^$@", "$@*^$@"),
            # All invalid passes through for prefix
            ("$@*^$@/name", "$@*^$@/name"),
        ],
    )
    async def test_sanitizes_user_label_keys(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_running_pod,
        mock_batch_client,
        given,
        expected,
    ):
        mock_watch.return_value.stream = mock_pods_stream_that_returns_running_pod
        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(),
            {
                "labels": {given: "foo"},
            },
        )
        configuration.prepare_for_flow_run(flow_run)

        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run, configuration)
            mock_batch_client.return_value.create_namespaced_job.assert_called_once()
            labels = mock_batch_client.return_value.create_namespaced_job.call_args[0][
                1
            ]["metadata"]["labels"]
            assert labels[expected] == "foo"

    @pytest.mark.parametrize(
        "given,expected",
        [
            ("valid-label-text", "valid-label-text"),
            (
                "text-with-invalid$@*^$@-characters",
                "text-with-invalid-characters",
            ),
            ("_value-that-starts-with-underscore", "value-that-starts-with-underscore"),
            ("-value-that-starts-with-dash", "value-that-starts-with-dash"),
            (".value-that-starts-with-period", "value-that-starts-with-period"),
            ("value-that-ends-with-underscore_", "value-that-ends-with-underscore"),
            ("value-that-ends-with-dash-", "value-that-ends-with-dash"),
            ("value-that-ends-with-period.", "value-that-ends-with-period"),
            (
                "._.-value-with-trailing-leading-chars-__-.",
                "value-with-trailing-leading-chars",
            ),
            # Truncation
            ("a" * 100, "a" * 63),
            # All invalid passes through
            ("$@*^$@", "$@*^$@"),
        ],
    )
    async def test_sanitizes_user_label_values(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_running_pod,
        mock_batch_client,
        given,
        expected,
    ):
        mock_watch.return_value.stream = mock_pods_stream_that_returns_running_pod

        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(),
            {"labels": {"foo": given}},
        )
        configuration.prepare_for_flow_run(flow_run)

        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run, configuration)
            mock_batch_client.return_value.create_namespaced_job.assert_called_once()
            labels = mock_batch_client.return_value.create_namespaced_job.call_args[0][
                1
            ]["metadata"]["labels"]
            assert labels["foo"] == expected

    async def test_uses_namespace_setting(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_running_pod,
        mock_batch_client,
    ):
        mock_watch.return_value.stream = mock_pods_stream_that_returns_running_pod
        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(),
            {"namespace": "foo"},
        )

        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run, configuration)
            mock_batch_client.return_value.create_namespaced_job.assert_called_once()
            namespace = mock_batch_client.return_value.create_namespaced_job.call_args[
                0
            ][1]["metadata"]["namespace"]
            assert namespace == "foo"

    async def test_allows_namespace_setting_from_manifest(
        self,
        flow_run,
        default_configuration,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_running_pod,
        mock_batch_client,
    ):
        mock_watch.return_value.stream = mock_pods_stream_that_returns_running_pod

        default_configuration.job_manifest["metadata"]["namespace"] = "test"
        default_configuration.prepare_for_flow_run(flow_run)

        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run, default_configuration)
            mock_batch_client.return_value.create_namespaced_job.assert_called_once()
            namespace = mock_batch_client.return_value.create_namespaced_job.call_args[
                0
            ][1]["metadata"]["namespace"]
            assert namespace == "test"

    async def test_uses_service_account_name_setting(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_running_pod,
        mock_batch_client,
    ):
        mock_watch.return_value.stream = mock_pods_stream_that_returns_running_pod
        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(),
            {"service_account_name": "foo"},
        )

        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run, configuration)
            mock_batch_client.return_value.create_namespaced_job.assert_called_once()
            service_account_name = (
                mock_batch_client.return_value.create_namespaced_job.call_args[0][1][
                    "spec"
                ]["template"]["spec"]["serviceAccountName"]
            )
            assert service_account_name == "foo"

    async def test_uses_finished_job_ttl_setting(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_running_pod,
        mock_batch_client,
    ):
        mock_watch.return_value.stream = mock_pods_stream_that_returns_running_pod
        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(),
            {"finished_job_ttl": 123},
        )

        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run, configuration)
            mock_batch_client.return_value.create_namespaced_job.assert_called_once()
            finished_job_ttl = (
                mock_batch_client.return_value.create_namespaced_job.call_args[0][1][
                    "spec"
                ]["ttlSecondsAfterFinished"]
            )
            assert finished_job_ttl == 123

    async def test_uses_specified_image_pull_policy(
        self,
        flow_run,
        mock_core_client,
        mock_watch,
        mock_pods_stream_that_returns_running_pod,
        mock_batch_client,
    ):
        mock_watch.return_value.stream = mock_pods_stream_that_returns_running_pod
        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(),
            {"image_pull_policy": "IfNotPresent"},
        )
        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run, configuration)
            mock_batch_client.return_value.create_namespaced_job.assert_called_once()
            call_image_pull_policy = (
                mock_batch_client.return_value.create_namespaced_job.call_args[0][1][
                    "spec"
                ]["template"]["spec"]["containers"][0].get("imagePullPolicy")
            )
            assert call_image_pull_policy == "IfNotPresent"

    @pytest.mark.usefixtures("mock_core_client_lean", "mock_cluster_config")
    async def test_keepalive_enabled(
        self,
    ):
        configuration = await KubernetesWorkerJobConfiguration.from_template_and_values(
            KubernetesWorker.get_default_base_job_template(),
            {"image": "foo"},
        )

        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            async with k8s_worker._get_configured_kubernetes_client(
                configuration
            ) as client:
                assert (
                    client.rest_client.pool_manager._request_class
                    is KeepAliveClientRequest
                )

    async def test_defaults_to_incluster_config(
        self,
        flow_run,
        default_configuration,
        mock_core_client_lean,
        mock_watch,
        mock_cluster_config,
        mock_batch_client,
        mock_job,
        mock_pod,
    ):
        async def mock_stream(*args, **kwargs):
            if kwargs["func"] == mock_core_client_lean.return_value.list_namespaced_pod:
                yield {"object": mock_pod, "type": "MODIFIED"}
            if kwargs["func"] == mock_core_client_lean.return_value.list_namespaced_job:
                mock_job.status.completion_time = DateTime.now("utc").timestamp()
                yield {"object": mock_job, "type": "MODIFIED"}

        mock_watch.return_value.stream = mock_stream

        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run, default_configuration)

            mock_cluster_config.load_incluster_config.assert_called_once()
            assert not mock_cluster_config.load_kube_config_from_dict.called

    async def test_uses_cluster_config_if_not_in_cluster(
        self,
        flow_run,
        default_configuration,
        mock_watch,
        mock_cluster_config,
        mock_batch_client,
        mock_core_client_lean,
        mock_job,
        mock_pod,
    ):
        async def mock_stream(*args, **kwargs):
            if kwargs["func"] == mock_core_client_lean.return_value.list_namespaced_pod:
                yield {"object": mock_pod, "type": "MODIFIED"}
            if kwargs["func"] == mock_core_client_lean.return_value.list_namespaced_job:
                mock_job.status.completion_time = DateTime.now("utc").timestamp()
                yield {"object": mock_job, "type": "MODIFIED"}

        mock_watch.return_value.stream = mock_stream
        mock_cluster_config.load_incluster_config.side_effect = ConfigException()

        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(flow_run, default_configuration)
            mock_cluster_config.new_client_from_config.assert_called_once()

    class TestPodWatch:
        @pytest.mark.parametrize("job_timeout", [24, 100])
        async def test_allows_configurable_timeouts_for_pod_and_job_watches(
            self,
            mock_core_client,
            mock_watch,
            mock_batch_client,
            job_timeout,
            default_configuration: KubernetesWorkerJobConfiguration,
            flow_run,
            mock_pod,
            mock_job,
        ):
            async def mock_stream(*args, **kwargs):
                mock_job.status.completion_time = DateTime.now("utc").timestamp()
                stream = [
                    {"object": mock_job, "type": "MODIFIED"},
                    {"object": mock_pod, "type": "MODIFIED"},
                ]
                for item in stream:
                    yield item

            mock_watch.return_value.stream = mock.Mock(side_effect=mock_stream)

            # The job should not be completed to start
            mock_batch_client.return_value.read_namespaced_job.return_value.status.completion_time = None

            k8s_job_args = dict(
                command=["echo", "hello"],
                pod_watch_timeout_seconds=42,
            )
            expected_job_call_kwargs = dict(
                func=mock_batch_client.return_value.list_namespaced_job,
                namespace=mock.ANY,
                field_selector=mock.ANY,
            )

            if job_timeout is not None:
                k8s_job_args["job_watch_timeout_seconds"] = job_timeout
                expected_job_call_kwargs["timeout_seconds"] = pytest.approx(
                    job_timeout, abs=1
                )

            default_configuration.job_watch_timeout_seconds = job_timeout
            default_configuration.pod_watch_timeout_seconds = 42

            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                await k8s_worker.run(flow_run, default_configuration)

            mock_watch.return_value.stream.assert_has_calls(
                [
                    mock.call(
                        func=mock_core_client.return_value.list_namespaced_pod,
                        namespace=mock.ANY,
                        label_selector=mock.ANY,
                        timeout_seconds=42,
                    ),
                    mock.call(**expected_job_call_kwargs),
                ]
            )

        @pytest.mark.parametrize("job_timeout", [None])
        async def test_excludes_timeout_from_job_watches_when_null(
            self,
            flow_run,
            default_configuration,
            mock_core_client,
            mock_watch,
            mock_pods_stream_that_returns_running_pod,
            mock_batch_client,
            job_timeout,
            mock_pod,
            mock_job,
        ):
            async def mock_stream(*args, **kwargs):
                mock_job.status.completion_time = DateTime.now("utc").timestamp()
                stream = [
                    {"object": mock_job, "type": "MODIFIED"},
                    {"object": mock_pod, "type": "MODIFIED"},
                ]
                for item in stream:
                    yield item

            mock_watch.return_value.stream = mock.Mock(side_effect=mock_stream)
            # The job should not be completed to start
            mock_batch_client.return_value.read_namespaced_job.return_value.status.completion_time = None

            default_configuration.job_watch_timeout_seconds = job_timeout

            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                await k8s_worker.run(flow_run, default_configuration)

            mock_watch.return_value.stream.assert_has_calls(
                [
                    mock.call(
                        func=mock_core_client.return_value.list_namespaced_pod,
                        namespace=mock.ANY,
                        label_selector=mock.ANY,
                        timeout_seconds=mock.ANY,
                    ),
                    mock.call(
                        func=mock_batch_client.return_value.list_namespaced_job,
                        namespace=mock.ANY,
                        field_selector=mock.ANY,
                        # Note: timeout_seconds is excluded here
                    ),
                ]
            )

        async def test_watches_the_right_namespace(
            self,
            flow_run,
            default_configuration,
            mock_core_client,
            mock_watch,
            mock_batch_client,
            mock_pod,
            mock_job,
        ):
            async def mock_stream(*args, **kwargs):
                mock_job.status.completion_time = DateTime.now("utc").timestamp()
                stream = [
                    {"object": mock_job, "type": "MODIFIED"},
                    {"object": mock_pod, "type": "MODIFIED"},
                ]
                for item in stream:
                    yield item

            mock_watch.return_value.stream = mock.Mock(side_effect=mock_stream)
            # The job should not be completed to start
            mock_batch_client.return_value.read_namespaced_job.return_value.status.completion_time = None
            default_configuration.namespace = "my-awesome-flows"
            default_configuration.prepare_for_flow_run(flow_run)

            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                await k8s_worker.run(flow_run, default_configuration)

            mock_watch.return_value.stream.assert_has_calls(
                [
                    mock.call(
                        func=mock_core_client.return_value.list_namespaced_pod,
                        namespace="my-awesome-flows",
                        label_selector=mock.ANY,
                        timeout_seconds=60,
                    ),
                    mock.call(
                        func=mock_batch_client.return_value.list_namespaced_job,
                        namespace="my-awesome-flows",
                        field_selector=mock.ANY,
                    ),
                ]
            )

        async def test_streaming_pod_logs_timeout_warns(
            self,
            flow_run,
            default_configuration: KubernetesWorkerJobConfiguration,
            mock_core_client,
            mock_watch,
            mock_batch_client,
            caplog,
            mock_pod,
            mock_job,
        ):
            job_pod = MagicMock(spec=kubernetes_asyncio.client.V1Pod)
            mock_container_status = MagicMock(
                spec=kubernetes_asyncio.client.V1ContainerStatus
            )
            mock_container_status.state.running = None
            mock_container_status.state.waiting = None
            job_pod.status.container_statuses = [mock_container_status]
            mock_core_client.return_value.list_namespaced_pod.return_value.items = [
                job_pod
            ]

            async def mock_stream(*args, **kwargs):
                mock_job.status.completion_time = DateTime.now("utc").timestamp()
                stream = [
                    {"object": mock_job, "type": "MODIFIED"},
                    {"object": mock_pod, "type": "MODIFIED"},
                ]
                for item in stream:
                    yield item

            mock_watch.return_value.stream = mock.Mock(side_effect=mock_stream)
            # The job should not be completed to start
            mock_batch_client.return_value.read_namespaced_job.return_value.status.completion_time = None

            async def mock_log_stream(*args, **kwargs):
                yield RuntimeError("something went wrong")

            mock_core_client.return_value.read_namespaced_pod_log.return_value.content = mock_log_stream
            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                with caplog.at_level("WARNING"):
                    result = await k8s_worker.run(flow_run, default_configuration)

            assert result.status_code == 1
            assert "Error occurred while streaming logs - " in caplog.text

        async def test_watch_timeout(
            self,
            mock_core_client,
            mock_watch,
            mock_batch_client,
            flow_run,
            default_configuration,
            mock_pod,
        ):
            # The job should not be completed to start
            mock_batch_client.return_value.read_namespaced_job.return_value.status.completion_time = None

            async def mock_stream(*args, **kwargs):
                if kwargs["func"] == mock_core_client.return_value.list_namespaced_pod:
                    yield {"object": mock_pod, "type": "ADDED"}

                if kwargs["func"] == mock_batch_client.return_value.list_namespaced_job:
                    job = MagicMock(spec=kubernetes_asyncio.client.V1Job)
                    job.status.completion_time = None
                    yield {"object": job, "type": "ADDED"}
                    sleep(0.5)
                    yield {"object": job, "type": "ADDED"}

            default_configuration.pod_watch_timeout_seconds = 42
            default_configuration.job_watch_timeout_seconds = 0
            mock_watch.return_value.stream = mock.Mock(side_effect=mock_stream)

            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                result = await k8s_worker.run(flow_run, default_configuration)
                assert result.status_code == -1

        async def test_watch_deadline_is_computed_before_log_streams(
            self,
            flow_run,
            default_configuration,
            mock_core_client,
            mock_watch,
            mock_batch_client,
            mock_pod,
        ):
            # The job should not be completed to start
            mock_batch_client.return_value.read_namespaced_job.return_value.status.completion_time = None

            async def mock_stream(*args, **kwargs):
                if kwargs["func"] == mock_core_client.return_value.list_namespaced_pod:
                    yield {"object": mock_pod, "type": "MODIFIED"}

                if kwargs["func"] == mock_batch_client.return_value.list_namespaced_job:
                    job = MagicMock(spec=kubernetes_asyncio.client.V1Job)

                    # Yield the completed job
                    job.status.completion_time = True
                    job.status.failed = 0
                    job.spec.backoff_limit = 6
                    yield {"object": job, "type": "ADDED"}

            async def mock_log_stream(*args, **kwargs):
                await anyio.sleep(50)
                yield MagicMock()

            mock_core_client.return_value.read_namespaced_pod_log.return_value.stream = mock_log_stream
            mock_watch.return_value.stream = mock.Mock(side_effect=mock_stream)
            job_pod = MagicMock(spec=kubernetes_asyncio.client.V1Pod)
            mock_container_status = MagicMock(
                spec=kubernetes_asyncio.client.V1ContainerStatus
            )
            mock_container_status.state.running = None
            mock_container_status.state.waiting = None
            job_pod.status.container_statuses = [mock_container_status]
            mock_core_client.return_value.list_namespaced_pod.return_value.items = [
                job_pod
            ]

            default_configuration.job_watch_timeout_seconds = 100
            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                result = await k8s_worker.run(flow_run, default_configuration)

            assert result.status_code == 1

            mock_watch.return_value.stream.assert_has_calls(
                [
                    mock.call(
                        func=mock_core_client.return_value.list_namespaced_pod,
                        namespace=mock.ANY,
                        label_selector=mock.ANY,
                        timeout_seconds=mock.ANY,
                    ),
                    # Starts with the full timeout minus the amount we slept streaming logs
                    mock.call(
                        func=mock_batch_client.return_value.list_namespaced_job,
                        field_selector=mock.ANY,
                        namespace=mock.ANY,
                        timeout_seconds=pytest.approx(50, 1),
                    ),
                ]
            )

        async def test_watch_timeout_is_restarted_until_job_is_complete(
            self,
            flow_run,
            default_configuration,
            mock_core_client,
            mock_watch,
            mock_batch_client,
            mock_pod,
        ):
            # The job should not be completed to start
            mock_batch_client.return_value.read_namespaced_job.return_value.status.completion_time = None

            # TODO investigate why it needs type
            async def mock_stream(*args, **kwargs):
                if kwargs["func"] == mock_core_client.return_value.list_namespaced_pod:
                    yield {"object": mock_pod, "type": "MODIFIED"}

                if kwargs["func"] == mock_batch_client.return_value.list_namespaced_job:
                    job = MagicMock(spec=kubernetes_asyncio.client.V1Job)

                    # Sleep a little
                    await anyio.sleep(10)

                    # Yield the job then return exiting the stream
                    job.status.completion_time = None
                    job.status.failed = 0
                    job.spec.backoff_limit = 6
                    yield {"object": job, "type": "ADDED"}

            # mock_watch.return_value.stream = mock_stream
            mock_watch.return_value.stream = mock.Mock(side_effect=mock_stream)
            default_configuration.job_watch_timeout_seconds = 1
            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                result = await k8s_worker.run(flow_run, default_configuration)

            assert result.status_code == -1

        async def test_watch_stops_after_backoff_limit_reached(
            self,
            flow_run,
            default_configuration,
            mock_core_client,
            mock_watch,
            mock_batch_client,
            mock_pod,
        ):
            # The job should not be completed to start
            mock_batch_client.return_value.read_namespaced_job.return_value.status.completion_time = None
            job_pod = MagicMock(spec=kubernetes_asyncio.client.V1Pod)
            job_pod.status.phase = "Running"
            mock_container_status = MagicMock(
                spec=kubernetes_asyncio.client.V1ContainerStatus
            )
            mock_container_status.state.terminated.exit_code = 137
            mock_container_status.state.running = None
            mock_container_status.state.waiting = None
            job_pod.status.container_statuses = [mock_container_status]
            mock_core_client.return_value.list_namespaced_pod.return_value.items = [
                job_pod
            ]

            # TODO investigate why it needs type
            async def mock_stream(*args, **kwargs):
                if kwargs["func"] == mock_core_client.return_value.list_namespaced_pod:
                    yield {"object": mock_pod, "type": "ADDED"}

                if kwargs["func"] == mock_batch_client.return_value.list_namespaced_job:
                    job = MagicMock(spec=kubernetes_asyncio.client.V1Job)

                    # Yield the job then return exiting the stream
                    job.status.completion_time = None
                    job.spec.backoff_limit = 6
                    for i in range(0, 8):
                        job.status.failed = i
                        yield {"object": job, "type": "ADDED"}

            mock_watch.return_value.stream = mock.Mock(side_effect=mock_stream)

            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                result = await k8s_worker.run(flow_run, default_configuration)

            assert result.status_code == 137

        async def test_watch_handles_no_pod(
            self,
            flow_run,
            default_configuration,
            mock_core_client,
            mock_watch,
            mock_batch_client,
            mock_pod,
        ):
            # The job should not be completed to start
            mock_batch_client.return_value.read_namespaced_job.return_value.status.completion_time = None
            mock_core_client.return_value.list_namespaced_pod.return_value.items = []

            # TODO investigate why it needs type
            async def mock_stream(*args, **kwargs):
                if kwargs["func"] == mock_core_client.return_value.list_namespaced_pod:
                    yield {"object": mock_pod, "type": "ADDED"}

                if kwargs["func"] == mock_batch_client.return_value.list_namespaced_job:
                    job = MagicMock(spec=kubernetes_asyncio.client.V1Job)

                    # Yield the job then return exiting the stream
                    job.status.completion_time = None
                    job.spec.backoff_limit = 6
                    for i in range(0, 8):
                        job.status.failed = i
                        yield {"object": job, "type": "ADDED"}

            mock_watch.return_value.stream = mock.Mock(side_effect=mock_stream)

            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                k8s_worker._client = AsyncMock()
                mock_flow_run = MagicMock(spec=FlowRun)
                mock_flow_run.state = Running()
                k8s_worker._client.read_flow_run.return_value = mock_flow_run
                result = await k8s_worker.run(flow_run, default_configuration)

            assert result.status_code == -1

        async def test_watch_handles_pod_without_exit_code(
            self,
            flow_run,
            default_configuration,
            mock_core_client,
            mock_watch,
            mock_batch_client,
            mock_pod,
        ):
            """
            This test case mimics the behavior of a pod that has been forcefully terminated
            (i.e. AWS spot instance termination or another node failure).
            """
            mock_batch_client.return_value.read_namespaced_job.return_value.status.completion_time = None
            job_pod = MagicMock(spec=kubernetes_asyncio.client.V1Pod)
            job_pod.status.phase = "Running"
            mock_container_status = MagicMock(
                spec=kubernetes_asyncio.client.V1ContainerStatus
            )
            # The container may exist but because it has been forcefully terminated
            # it will not have an exit code.
            mock_container_status.state.terminated = None
            mock_container_status.state.running = None
            mock_container_status.state.waiting = None
            job_pod.status.container_statuses = [mock_container_status]
            mock_core_client.return_value.list_namespaced_pod.return_value.items = [
                job_pod
            ]

            # TODO investigate why it needs type
            async def mock_stream(*args, **kwargs):
                if kwargs["func"] == mock_core_client.return_value.list_namespaced_pod:
                    yield {"object": mock_pod, "type": "ADDED"}

                if kwargs["func"] == mock_batch_client.return_value.list_namespaced_job:
                    job = MagicMock(spec=kubernetes_asyncio.client.V1Job)

                    # Yield the job then return exiting the stream
                    job.status.completion_time = None
                    job.spec.backoff_limit = 6
                    for i in range(0, 8):
                        job.status.failed = i
                        yield {"object": job, "type": "ADDED"}

            mock_watch.return_value.stream = mock.Mock(side_effect=mock_stream)

            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                result = await k8s_worker.run(flow_run, default_configuration)

            assert result.status_code == -1

        async def test_watch_handles_410(
            self,
            default_configuration: KubernetesWorkerJobConfiguration,
            flow_run,
            mock_batch_client,
            mock_core_client,
            mock_watch,
            mock_job,
            mock_pod,
        ):
            async def mock_stream(*args, **kwargs):
                mock_job.status.completion_time = DateTime.now("utc").timestamp()
                items = [
                    {"object": mock_pod, "type": "MODIFIED"},
                    {"object": mock_job, "type": "MODIFIED"},
                ]
                for item in items:
                    yield item

            stream_return = [
                mock_stream(),
                mock_stream(),
                ApiException(status=410),
                mock_stream(),
            ]
            mock_watch.return_value.stream = mock.Mock(side_effect=stream_return)
            job_list = MagicMock(spec=kubernetes_asyncio.client.V1JobList)
            job_list.metadata.resource_version = "1"

            mock_batch_client.return_value.list_namespaced_job.side_effect = [job_list]

            # The job should not be completed to start
            mock_batch_client.return_value.read_namespaced_job.return_value.status.completion_time = None

            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                await k8s_worker.run(
                    flow_run=flow_run, configuration=default_configuration
                )

            mock_watch.return_value.stream.assert_has_calls(
                [
                    mock.call(
                        func=mock_batch_client.return_value.list_namespaced_job,
                        namespace=mock.ANY,
                        field_selector="metadata.name=mock-job",
                    ),
                    mock.call(
                        func=mock_batch_client.return_value.list_namespaced_job,
                        namespace=mock.ANY,
                        field_selector="metadata.name=mock-job",
                        resource_version="1",
                    ),
                ]
            )

        async def test_watch_early_exit(
            self,
            default_configuration: KubernetesWorkerJobConfiguration,
            flow_run,
            mock_batch_client,
            mock_core_client,
            mock_watch,
            mock_job,
            mock_pod,
        ):
            mock_batch_client.return_value.read_namespaced_job.return_value.status.completion_time = None
            job_pod = MagicMock(spec=kubernetes_asyncio.client.V1Pod)
            job_pod.status.phase = "Running"
            mock_container_status = MagicMock(
                spec=kubernetes_asyncio.client.V1ContainerStatus
            )
            mock_container_status.state.running = MagicMock(
                start_time=DateTime.now("utc")
            )
            job_pod.status.container_statuses = [mock_container_status]
            mock_core_client.return_value.list_namespaced_pod.return_value.items = [
                job_pod
            ]

            async def mock_stream(*args, **kwargs):
                if kwargs["func"] == mock_core_client.return_value.list_namespaced_pod:
                    yield {"object": mock_pod, "type": "ADDED"}

                if kwargs["func"] == mock_batch_client.return_value.list_namespaced_job:
                    raise Exception("This is a test exception")

            mock_watch.return_value.stream = mock.Mock(side_effect=mock_stream)

            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                result = await k8s_worker.run(flow_run, default_configuration)

            assert result.status_code == 0

        async def test_watch_no_timeout_after_five_minutes_without_data(
            self,
            flow_run,
            default_configuration,
            mock_core_client,
            mock_watch,
            mock_batch_client,
            mock_pod,
            caplog: pytest.LogCaptureFixture,
        ):
            """
            Regressio test for https://github.com/PrefectHQ/prefect/issues/16210
            """
            # The job should not be completed to start
            mock_batch_client.return_value.read_namespaced_job.return_value.status.completion_time = None

            async def mock_stream(*args, **kwargs):
                if kwargs["func"] == mock_core_client.return_value.list_namespaced_pod:
                    yield {"object": mock_pod, "type": "MODIFIED"}

                if kwargs["func"] == mock_batch_client.return_value.list_namespaced_job:
                    job = MagicMock(spec=kubernetes_asyncio.client.V1Job)
                    job.status.completion_time = None
                    job.status.failed = 0
                    job.spec.backoff_limit = 6

                    # First event
                    yield {"object": job, "type": "ADDED"}

                    # Simulate 5 minutes passing
                    with patch("anyio.sleep", return_value=None):
                        await anyio.sleep(310)

                    # Send another event after the delay
                    job.status.completion_time = DateTime.now("utc").timestamp()
                    yield {"object": job, "type": "MODIFIED"}

            mock_watch.return_value.stream = mock.Mock(side_effect=mock_stream)

            async with KubernetesWorker(work_pool_name="test") as k8s_worker:
                result = await k8s_worker.run(flow_run, default_configuration)
            assert "Error occurred while streaming logs" not in caplog.text
            assert result.status_code == 0

    @pytest.fixture
    async def mock_events(self, mock_core_client):
        mock_core_client.return_value.list_namespaced_event.return_value = (
            CoreV1EventList(
                metadata=V1ListMeta(resource_version="1"),
                items=[
                    CoreV1Event(
                        metadata=V1ObjectMeta(),
                        involved_object=V1ObjectReference(
                            api_version="batch/v1",
                            kind="Job",
                            namespace="default",
                            name="mock-job",
                        ),
                        reason="StuffBlewUp",
                        count=2,
                        last_timestamp=parse_datetime("2022-01-02T03:04:05Z"),
                        message="Whew, that was baaaaad",
                    ),
                    CoreV1Event(
                        metadata=V1ObjectMeta(),
                        involved_object=V1ObjectReference(
                            api_version="batch/v1",
                            kind="Job",
                            namespace="default",
                            name="this-aint-me",  # not my flow run ID
                        ),
                        reason="NahChief",
                        count=2,
                        last_timestamp=parse_datetime("2022-01-02T03:04:05Z"),
                        message="You do not want to know about this one",
                    ),
                    CoreV1Event(
                        metadata=V1ObjectMeta(),
                        involved_object=V1ObjectReference(
                            api_version="v1",
                            kind="Pod",
                            namespace="default",
                            name="my-pod",
                        ),
                        reason="ImageWhatImage",
                        count=1,
                        event_time=parse_datetime("2022-01-02T03:04:05Z"),
                        message="I don't see no image",
                    ),
                    CoreV1Event(
                        metadata=V1ObjectMeta(),
                        involved_object=V1ObjectReference(
                            api_version="v1",
                            kind="Pod",
                            namespace="default",
                            name="my-pod",
                        ),
                        reason="GoodLuck",
                        count=1,
                        last_timestamp=parse_datetime("2022-01-02T03:04:05Z"),
                        message="You ain't getting no more RAM",
                    ),
                    CoreV1Event(
                        metadata=V1ObjectMeta(),
                        involved_object=V1ObjectReference(
                            api_version="v1",
                            kind="Pod",
                            namespace="default",
                            name="somebody-else",  # not my pod
                        ),
                        reason="NotMeDude",
                        count=1,
                        last_timestamp=parse_datetime("2022-01-02T03:04:05Z"),
                        message="You ain't getting no more RAM",
                    ),
                    CoreV1Event(
                        metadata=V1ObjectMeta(),
                        involved_object=V1ObjectReference(
                            api_version="batch/v1",
                            kind="Job",
                            namespace="default",
                            name="mock-job",
                        ),
                        reason="StuffBlewUp",
                        count=2,
                        last_timestamp=parse_datetime("2022-01-02T03:04:05Z"),
                        message="I mean really really bad",
                    ),
                ],
            )
        )

    async def test_explains_what_might_have_gone_wrong_in_scheduling_the_pod(
        self,
        default_configuration: KubernetesWorkerJobConfiguration,
        flow_run,
        mock_batch_client,
        mock_core_client: mock.Mock,
        mock_watch,
        mock_events,
        caplog: pytest.LogCaptureFixture,
    ):
        """Regression test for #87, where workers were giving only very vague
        information about the reason a pod was never scheduled."""

        async def mock_stream(*args, **kwargs):
            if kwargs["func"] == mock_batch_client.return_value.list_namespaced_job:
                job = MagicMock(spec=kubernetes_asyncio.client.V1Job)
                yield {"object": job, "type": "ADDED"}

        mock_watch.return_value.stream = mock.Mock(side_effect=mock_stream)
        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            await k8s_worker.run(
                flow_run=flow_run,
                configuration=default_configuration,
                task_status=MagicMock(spec=anyio.abc.TaskStatus),
            )

            mock_core_client.return_value.list_namespaced_event.assert_called_once_with(
                default_configuration.namespace
            )

            # The original error log should still be included
            assert "Pod never started" in caplog.text

            # The events for the job should be included
            assert "StuffBlewUp" in caplog.text
            assert "Whew, that was baaaaad" in caplog.text
            assert "I mean really really bad" in caplog.text

            # The event for another job shouldn't be included
            assert "NahChief" not in caplog.text

    async def test_explains_what_might_have_gone_wrong_in_starting_the_pod(
        self,
        default_configuration: KubernetesWorkerJobConfiguration,
        flow_run,
        mock_core_client: mock.Mock,
        mock_events,
        caplog: pytest.LogCaptureFixture,
    ):
        """Regression test for #90, where workers were giving only very vague
        information about the reason a pod never started.  This does not attempt to
        run the flow, but rather just tests the logging method directly."""
        async with KubernetesWorker(work_pool_name="test") as k8s_worker:
            logger = k8s_worker.get_flow_run_logger(flow_run)

            mock_client = mock.Mock()
            await k8s_worker._log_recent_events(
                logger, "mock-job", "my-pod", default_configuration, mock_client
            )

            # The events for the pod should be included
            assert "ImageWhatImage" in caplog.text
            assert "You ain't getting no more RAM" in caplog.text

            # The event for another job or pod shouldn't be included
            assert "NahChief" not in caplog.text
            assert "NotMeDude" not in caplog.text

    class TestSubmit:
        @pytest.fixture
        async def work_pool(self):
            async with prefect.get_client() as client:
                work_pool = await client.create_work_pool(
                    WorkPoolCreate(
                        name=f"test-{uuid.uuid4()}",
                        base_job_template=KubernetesWorker.get_default_base_job_template(),
                    )
                )
                try:
                    yield work_pool
                finally:
                    await client.delete_work_pool(work_pool.name)

        @pytest.fixture(autouse=True)
        async def mock_steps(
            self, work_pool: WorkPool, monkeypatch: pytest.MonkeyPatch
        ):
            UPLOAD_STEP = {
                "prefect_mock.experimental.bundles.upload": {
                    "requires": "prefect-mock==0.5.5",
                    "bucket": "test-bucket",
                    "credentials_block_name": "my-creds",
                }
            }

            EXECUTE_STEP = {
                "prefect_mock.experimental.bundles.execute": {
                    "requires": "prefect-mock==0.5.5",
                    "bucket": "test-bucket",
                    "credentials_block_name": "my-creds",
                }
            }

            async with prefect.get_client() as client:
                work_pool.base_job_template["variables"]["properties"]["env"][
                    "default"
                ] = {
                    "PREFECT__BUNDLE_UPLOAD_STEP": json.dumps(UPLOAD_STEP),
                    "PREFECT__BUNDLE_EXECUTE_STEP": json.dumps(EXECUTE_STEP),
                }
                await client.update_work_pool(
                    work_pool.name,
                    WorkPoolUpdate(base_job_template=work_pool.base_job_template),
                )

        @pytest.fixture
        def test_flow(self):
            @prefect.flow
            def my_flow():
                return "Hello, world!"

            return my_flow

        async def test_submit_adhoc_run(
            self,
            mock_batch_client,
            mock_core_client,
            mock_watch,
            mock_events,
            mock_pods_stream_that_returns_completed_pod,
            default_configuration,
            test_flow,
            mock_run_process: AsyncMock,
            caplog: pytest.LogCaptureFixture,
            work_pool: WorkPool,
        ):
            mock_watch.return_value.stream = mock.Mock(
                side_effect=mock_pods_stream_that_returns_completed_pod
            )
            python_version_info = sys.version_info
            async with KubernetesWorker(work_pool_name=work_pool.name) as k8s_worker:
                future = await k8s_worker.submit(test_flow)
                assert isinstance(future, PrefectFlowRunFuture)
            expected_command = [
                "uv",
                "run",
                "--with",
                "prefect-mock==0.5.5",
                "--python",
                f"{python_version_info.major}.{python_version_info.minor}",
                "-m",
                "prefect_mock.experimental.bundles.upload",
                "--bucket",
                "test-bucket",
                "--credentials-block-name",
                "my-creds",
                "--key",
                str(future.flow_run_id),
                str(future.flow_run_id),
            ]
            mock_run_process.assert_called_once_with(
                expected_command,
                cwd=ANY,
            )

        async def test_submit_adhoc_run_failed_submission(
            self,
            mock_batch_client,
            mock_core_client,
            mock_watch,
            mock_events,
            mock_pods_stream_that_returns_completed_pod,
            default_configuration,
            test_flow,
            mock_run_process: AsyncMock,
            caplog: pytest.LogCaptureFixture,
            work_pool: WorkPool,
        ):
            response = MagicMock()
            response.data = None
            response.status = 403
            response.reason = "Test"

            mock_batch_client.return_value.create_namespaced_job.side_effect = (
                ApiException(http_resp=response)
            )

            async with KubernetesWorker(work_pool_name=work_pool.name) as k8s_worker:
                future = await k8s_worker.submit(test_flow)
                assert isinstance(future, PrefectFlowRunFuture)

            async with prefect.get_client() as client:
                flow_run = await client.read_flow_run(future.flow_run_id)
                assert flow_run.state.is_crashed()

        async def test_submit_adhoc_run_non_zero_exit_code(
            self,
            mock_batch_client,
            mock_core_client,
            mock_watch,
            mock_events,
            mock_pods_stream_that_returns_completed_pod,
            default_configuration,
            test_flow,
            mock_run_process: AsyncMock,
            caplog: pytest.LogCaptureFixture,
            work_pool: WorkPool,
        ):
            mock_watch.return_value.stream = mock.Mock(
                side_effect=mock_pods_stream_that_returns_completed_pod
            )
            mock_batch_client.return_value.read_namespaced_job.return_value.status.completion_time = None
            job_pod = MagicMock(spec=kubernetes_asyncio.client.V1Pod)
            job_pod.status.phase = "Running"
            mock_container_status = MagicMock(
                spec=kubernetes_asyncio.client.V1ContainerStatus
            )
            mock_container_status.state.terminated.exit_code = 1
            mock_container_status.state.running = None
            mock_container_status.state.waiting = None
            job_pod.status.container_statuses = [mock_container_status]
            mock_core_client.return_value.list_namespaced_pod.return_value.items = [
                job_pod
            ]

            async with KubernetesWorker(work_pool_name=work_pool.name) as k8s_worker:
                future = await k8s_worker.submit(test_flow)
                assert isinstance(future, PrefectFlowRunFuture)

            async with prefect.get_client() as client:
                flow_run = await client.read_flow_run(future.flow_run_id)
                assert flow_run.state.is_crashed()
