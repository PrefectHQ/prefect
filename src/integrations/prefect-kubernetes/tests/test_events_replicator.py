import asyncio
import copy
import time
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from kubernetes_asyncio.client import V1Pod
from prefect_kubernetes.events import EVICTED_REASONS, KubernetesEventsReplicator

from prefect.events import RelatedResource
from prefect.utilities.importtools import lazy_import

kubernetes_asyncio = lazy_import("kubernetes_asyncio")


@pytest.fixture
async def client():
    async with AsyncMock() as mock:
        yield mock


@pytest.fixture
def pod():
    pod = MagicMock(spec=V1Pod)
    pod.metadata.name = "test-pod"
    pod.metadata.namespace = "test-namespace"
    pod.metadata.uid = "1234"
    return pod


@pytest.fixture
def pending_pod(pod):
    pending_pod = copy.deepcopy(pod)
    pending_pod.status.phase = "Pending"
    return pending_pod


@pytest.fixture
def running_pod(pod):
    running_pod = copy.deepcopy(pod)
    running_pod.status.phase = "Running"
    return running_pod


@pytest.fixture
def succeeded_pod(pod):
    succeeded_pod = copy.deepcopy(pod)
    succeeded_pod.status.phase = "Succeeded"
    return succeeded_pod


@pytest.fixture
def failed_pod(pod):
    failed_pod = copy.deepcopy(pod)
    failed_pod.status.phase = "Failed"
    return failed_pod


@pytest.fixture
def evicted_pod(pod):
    container_status = MagicMock()
    container_status.state.terminated.reason = "OOMKilled"

    assert container_status.state.terminated.reason in EVICTED_REASONS

    evicted_pod = copy.deepcopy(pod)
    evicted_pod.status.phase = "Failed"
    evicted_pod.status.container_statuses = [container_status]

    return evicted_pod


@pytest.fixture
async def successful_pod_stream(pending_pod, running_pod, succeeded_pod):
    async def event_stream():
        events = [
            {"type": "ADDED", "object": pending_pod},
            {"type": "MODIFIED", "object": running_pod},
            {"type": "MODIFIED", "object": succeeded_pod},
        ]
        for event in events:
            yield event
            await asyncio.sleep(0.1)  # simulate async behavior

    return event_stream()


@pytest.fixture
def failed_pod_stream(pending_pod, running_pod, failed_pod):
    async def event_stream():
        events = [
            {
                "type": "ADDED",
                "object": pending_pod,
            },
            {
                "type": "MODIFIED",
                "object": running_pod,
            },
            {
                "type": "MODIFIED",
                "object": failed_pod,
            },
        ]
        for event in events:
            yield event
            await asyncio.sleep(0.1)  # simulate async behavior

    return event_stream()


@pytest.fixture
def evicted_pod_stream(pending_pod, running_pod, evicted_pod):
    async def event_stream():
        events = [
            {
                "type": "ADDED",
                "object": pending_pod,
            },
            {
                "type": "MODIFIED",
                "object": running_pod,
            },
            {
                "type": "MODIFIED",
                "object": evicted_pod,
            },
        ]
        for event in events:
            yield event
            await asyncio.sleep(0.1)  # simulate async behavior

    return event_stream()


@pytest.fixture
def worker_resource():
    return {"prefect.resource.id": "prefect.worker.my-k8s-worker"}


@pytest.fixture
def related_resources():
    return [
        RelatedResource(
            {
                "prefect.resource.id": "prefect.flow-run.1234",
                "prefect.resource.role": "flow-run",
            }
        )
    ]


@pytest.fixture
def replicator(client, worker_resource, related_resources):
    return KubernetesEventsReplicator(
        client=client,
        job_name="test-job",
        namespace="test-namespace",
        worker_resource=worker_resource,
        related_resources=related_resources,
        timeout_seconds=60,
    )


async def test_lifecycle(replicator):
    mock_watch = AsyncMock(spec=kubernetes_asyncio.watch.Watch)

    with patch.object(replicator, "_watch", mock_watch):
        async with replicator:
            await asyncio.sleep(0.3)
            assert replicator._state == "STARTED"

    assert replicator._state == "STOPPED"


@pytest.mark.asyncio
async def test_replicate_successful_pod_events(replicator, successful_pod_stream):
    mock_watch = AsyncMock(spec=kubernetes_asyncio.watch.Watch)
    mock_watch.stream.return_value = successful_pod_stream

    event_count = 0

    def event(*args, **kwargs):
        nonlocal event_count
        event_count += 1
        return event_count

    with patch("prefect_kubernetes.events.emit_event", side_effect=event) as mock_emit:
        with patch.object(replicator, "_watch", mock_watch):
            async with replicator:
                await asyncio.sleep(
                    0.5
                )  # allow some time for the events to be processed

    mock_emit.assert_has_calls(
        [
            call(
                event="prefect.kubernetes.pod.pending",
                resource={
                    "prefect.resource.id": "prefect.kubernetes.pod.1234",
                    "prefect.resource.name": "test-pod",
                    "kubernetes.namespace": "test-namespace",
                },
                related=[
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.flow-run.1234",
                            "prefect.resource.role": "flow-run",
                        }
                    ),
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.worker.my-k8s-worker",
                            "prefect.resource.role": "worker",
                        }
                    ),
                ],
                follows=None,
            ),
            call(
                event="prefect.kubernetes.pod.running",
                resource={
                    "prefect.resource.id": "prefect.kubernetes.pod.1234",
                    "prefect.resource.name": "test-pod",
                    "kubernetes.namespace": "test-namespace",
                },
                related=[
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.flow-run.1234",
                            "prefect.resource.role": "flow-run",
                        }
                    ),
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.worker.my-k8s-worker",
                            "prefect.resource.role": "worker",
                        }
                    ),
                ],
                follows=1,
            ),
            call(
                event="prefect.kubernetes.pod.succeeded",
                resource={
                    "prefect.resource.id": "prefect.kubernetes.pod.1234",
                    "prefect.resource.name": "test-pod",
                    "kubernetes.namespace": "test-namespace",
                },
                related=[
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.flow-run.1234",
                            "prefect.resource.role": "flow-run",
                        }
                    ),
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.worker.my-k8s-worker",
                            "prefect.resource.role": "worker",
                        }
                    ),
                ],
                follows=2,
            ),
        ]
    )
    mock_watch.stop.assert_called_once_with()


@pytest.mark.asyncio
async def test_replicate_failed_pod_events(replicator, failed_pod_stream):
    mock_watch = AsyncMock(spec=kubernetes_asyncio.watch.Watch)
    mock_watch.stream.return_value = failed_pod_stream

    event_count = 0

    def event(*args, **kwargs):
        nonlocal event_count
        event_count += 1
        return event_count

    with patch("prefect_kubernetes.events.emit_event", side_effect=event) as mock_emit:
        with patch.object(replicator, "_watch", mock_watch):
            async with replicator:
                time.sleep(0.3)

    mock_emit.assert_has_calls(
        [
            call(
                event="prefect.kubernetes.pod.pending",
                resource={
                    "prefect.resource.id": "prefect.kubernetes.pod.1234",
                    "prefect.resource.name": "test-pod",
                    "kubernetes.namespace": "test-namespace",
                },
                related=[
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.flow-run.1234",
                            "prefect.resource.role": "flow-run",
                        }
                    ),
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.worker.my-k8s-worker",
                            "prefect.resource.role": "worker",
                        }
                    ),
                ],
                follows=None,
            ),
            call(
                event="prefect.kubernetes.pod.running",
                resource={
                    "prefect.resource.id": "prefect.kubernetes.pod.1234",
                    "prefect.resource.name": "test-pod",
                    "kubernetes.namespace": "test-namespace",
                },
                related=[
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.flow-run.1234",
                            "prefect.resource.role": "flow-run",
                        }
                    ),
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.worker.my-k8s-worker",
                            "prefect.resource.role": "worker",
                        }
                    ),
                ],
                follows=1,
            ),
            call(
                event="prefect.kubernetes.pod.failed",
                resource={
                    "prefect.resource.id": "prefect.kubernetes.pod.1234",
                    "prefect.resource.name": "test-pod",
                    "kubernetes.namespace": "test-namespace",
                },
                related=[
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.flow-run.1234",
                            "prefect.resource.role": "flow-run",
                        }
                    ),
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.worker.my-k8s-worker",
                            "prefect.resource.role": "worker",
                        }
                    ),
                ],
                follows=2,
            ),
        ]
    )
    mock_watch.stop.assert_called_once_with()


@pytest.mark.asyncio
async def test_replicate_evicted_pod_events(replicator, evicted_pod_stream):
    mock_watch = AsyncMock(spec=kubernetes_asyncio.watch.Watch)
    mock_watch.stream.return_value = evicted_pod_stream

    event_count = 0

    def event(*args, **kwargs):
        nonlocal event_count
        event_count += 1
        return event_count

    with patch("prefect_kubernetes.events.emit_event", side_effect=event) as mock_emit:
        with patch.object(replicator, "_watch", mock_watch):
            async with replicator:
                await asyncio.sleep(0.3)

    mock_emit.assert_has_calls(
        [
            call(
                event="prefect.kubernetes.pod.pending",
                resource={
                    "prefect.resource.id": "prefect.kubernetes.pod.1234",
                    "prefect.resource.name": "test-pod",
                    "kubernetes.namespace": "test-namespace",
                },
                related=[
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.flow-run.1234",
                            "prefect.resource.role": "flow-run",
                        }
                    ),
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.worker.my-k8s-worker",
                            "prefect.resource.role": "worker",
                        }
                    ),
                ],
                follows=None,
            ),
            call(
                event="prefect.kubernetes.pod.running",
                resource={
                    "prefect.resource.id": "prefect.kubernetes.pod.1234",
                    "prefect.resource.name": "test-pod",
                    "kubernetes.namespace": "test-namespace",
                },
                related=[
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.flow-run.1234",
                            "prefect.resource.role": "flow-run",
                        }
                    ),
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.worker.my-k8s-worker",
                            "prefect.resource.role": "worker",
                        }
                    ),
                ],
                follows=1,
            ),
            call(
                event="prefect.kubernetes.pod.evicted",
                resource={
                    "prefect.resource.id": "prefect.kubernetes.pod.1234",
                    "prefect.resource.name": "test-pod",
                    "kubernetes.namespace": "test-namespace",
                    "kubernetes.reason": "OOMKilled",
                },
                related=[
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.flow-run.1234",
                            "prefect.resource.role": "flow-run",
                        }
                    ),
                    RelatedResource(
                        {
                            "prefect.resource.id": "prefect.worker.my-k8s-worker",
                            "prefect.resource.role": "worker",
                        }
                    ),
                ],
                follows=2,
            ),
        ]
    )
    mock_watch.stop.assert_called_once_with()
