import uuid
from contextlib import asynccontextmanager
from time import sleep
from unittest.mock import AsyncMock, MagicMock

import pytest
from prefect_kubernetes.observer import (
    _replicate_pod_event,
    start_observer,
    stop_observer,
)

from prefect.events.schemas.events import RelatedResource, Resource


@pytest.fixture
def mock_events_client(monkeypatch: pytest.MonkeyPatch):
    events_client = AsyncMock()

    @asynccontextmanager
    async def mock_get_events_client():
        try:
            yield events_client
        finally:
            pass

    monkeypatch.setattr(
        "prefect_kubernetes.observer.get_events_client", mock_get_events_client
    )
    monkeypatch.setattr("prefect_kubernetes.observer.events_client", events_client)
    return events_client


@pytest.fixture
def mock_orchestration_client(monkeypatch: pytest.MonkeyPatch):
    orchestration_client = AsyncMock()
    json_response = MagicMock()
    json_response.json.return_value = {"events": [{"id": "existing-event"}]}
    orchestration_client.request.return_value = json_response

    @asynccontextmanager
    async def mock_get_orchestration_client():
        try:
            yield orchestration_client
        finally:
            pass

    monkeypatch.setattr(
        "prefect_kubernetes.observer.get_client",
        mock_get_orchestration_client,
    )
    monkeypatch.setattr(
        "prefect_kubernetes.observer.orchestration_client", orchestration_client
    )
    return orchestration_client


class TestReplicatePodEvent:
    async def test_minimal(self, mock_events_client: AsyncMock):
        flow_run_id = uuid.uuid4()
        pod_id = uuid.uuid4()

        await _replicate_pod_event(
            event={"type": "ADDED", "status": {"phase": "Running"}},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(flow_run_id),
                "prefect.io/flow-run-name": "test",
            },
            status={"phase": "Running"},
            logger=MagicMock(),
        )

        emitted_event = mock_events_client.emit.call_args[1]["event"]
        assert emitted_event.event == "prefect.kubernetes.pod.running"
        assert emitted_event.resource == Resource(
            {
                "prefect.resource.id": f"prefect.kubernetes.pod.{pod_id}",
                "prefect.resource.name": "test",
                "kubernetes.namespace": "test",
            }
        )
        assert emitted_event.related == [
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.flow-run.{flow_run_id}",
                    "prefect.resource.role": "flow-run",
                    "prefect.resource.name": "test",
                }
            )
        ]

    async def test_deterministic_event_id(self, mock_events_client: AsyncMock):
        """Test that the event ID is deterministic"""
        pod_id = uuid.uuid4()
        await _replicate_pod_event(
            event={"type": "ADDED", "status": {"phase": "Running"}},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(uuid.uuid4()),
                "prefect.io/flow-run-name": "test-run",
            },
            status={"phase": "Running"},
            logger=MagicMock(),
        )

        first_event_id = mock_events_client.emit.call_args[1]["event"].id
        mock_events_client.emit.reset_mock()

        # Call the function again
        await _replicate_pod_event(
            event={"type": "ADDED", "status": {"phase": "Running"}},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(uuid.uuid4()),
                "prefect.io/flow-run-name": "test-run",
            },
            status={"phase": "Running"},
            logger=MagicMock(),
        )

        second_event_id = mock_events_client.emit.call_args[1]["event"].id
        assert first_event_id == second_event_id

    async def test_evicted_pod(self, mock_events_client: AsyncMock):
        """Test handling of evicted pods"""
        pod_id = uuid.uuid4()

        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(uuid.uuid4()),
                "prefect.io/flow-run-name": "test-run",
            },
            status={
                "phase": "Failed",
                "container_statuses": [
                    {"state": {"terminated": {"reason": "OOMKilled"}}}
                ],
            },
            logger=MagicMock(),
        )

        emitted_event = mock_events_client.emit.call_args[1]["event"]
        assert emitted_event.event == "prefect.kubernetes.pod.evicted"
        assert emitted_event.resource == Resource(
            {
                "prefect.resource.id": f"prefect.kubernetes.pod.{pod_id}",
                "prefect.resource.name": "test",
                "kubernetes.namespace": "test",
                "kubernetes.reason": "OOMKilled",
            },
        )

    async def test_all_related_resources(self, mock_events_client: AsyncMock):
        """Test that all possible related resources are included"""
        flow_run_id = uuid.uuid4()
        deployment_id = uuid.uuid4()
        flow_id = uuid.uuid4()
        work_pool_id = uuid.uuid4()
        pod_id = uuid.uuid4()

        await _replicate_pod_event(
            event={"type": "ADDED"},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(flow_run_id),
                "prefect.io/flow-run-name": "test-run",
                "prefect.io/deployment-id": str(deployment_id),
                "prefect.io/deployment-name": "test-deployment",
                "prefect.io/flow-id": str(flow_id),
                "prefect.io/flow-name": "test-flow",
                "prefect.io/work-pool-id": str(work_pool_id),
                "prefect.io/work-pool-name": "test-pool",
                "prefect.io/worker-name": "test-worker",
            },
            status={"phase": "Running"},
            logger=MagicMock(),
        )

        mock_events_client.emit.assert_called_once()
        emitted_event = mock_events_client.emit.call_args[1]["event"]
        related_resources = emitted_event.related

        # Verify all related resources are present
        resource_ids = {
            r.model_dump()["prefect.resource.id"] for r in related_resources
        }
        assert resource_ids == {
            f"prefect.flow-run.{flow_run_id}",
            f"prefect.deployment.{deployment_id}",
            f"prefect.flow.{flow_id}",
            f"prefect.work-pool.{work_pool_id}",
            "prefect.worker.kubernetes.test-worker",
        }

        resource_names = {
            r.model_dump()["prefect.resource.name"] for r in related_resources
        }
        assert resource_names == {
            "test-run",
            "test-deployment",
            "test-flow",
            "test-pool",
            "test-worker",
        }

    @pytest.mark.usefixtures("mock_orchestration_client")
    async def test_event_deduplication(self, mock_events_client: AsyncMock):
        """Test that checks from existing events when receiving events on startup"""
        pod_id = uuid.uuid4()
        await _replicate_pod_event(
            # Event types with None are received when reading current cluster state
            event={"type": None},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels={"prefect.io/flow-run-id": str(uuid.uuid4())},
            status={"phase": "Running"},
            logger=MagicMock(),
        )

        # Verify no event was emitted since one already existed
        mock_events_client.emit.assert_not_called()

    @pytest.mark.parametrize("phase", ["Pending", "Running", "Succeeded", "Failed"])
    async def test_different_phases(self, mock_events_client: AsyncMock, phase: str):
        """Test handling of different pod phases"""
        pod_id = uuid.uuid4()
        flow_run_id = uuid.uuid4()

        mock_events_client.emit.reset_mock()
        await _replicate_pod_event(
            event={"type": "ADDED"},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(flow_run_id),
                "prefect.io/flow-run-name": "test-run",
            },
            status={"phase": phase},
            logger=MagicMock(),
        )

        mock_events_client.emit.assert_called_once()
        emitted_event = mock_events_client.emit.call_args[1]["event"]
        assert emitted_event.event == f"prefect.kubernetes.pod.{phase.lower()}"


class TestStartAndStopObserver:
    @pytest.mark.timeout(10)
    @pytest.mark.usefixtures("mock_events_client", "mock_orchestration_client")
    def test_start_and_stop(self, monkeypatch: pytest.MonkeyPatch):
        """
        Test that the observer can be started and stopped without errors
        and without hanging.
        """
        start_observer()
        sleep(1)
        stop_observer()
