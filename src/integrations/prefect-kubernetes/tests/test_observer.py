import uuid
from contextlib import asynccontextmanager
from time import sleep
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest
from prefect_kubernetes.observer import (
    _replicate_pod_event,
    start_observer,
    stop_observer,
)

from prefect.events.schemas.events import RelatedResource


class TestReplicatePodEvent:
    @pytest.fixture
    def mock_emit_event(self, monkeypatch: pytest.MonkeyPatch):
        mock = MagicMock()
        monkeypatch.setattr("prefect_kubernetes.observer.emit_event", mock)
        return mock

    async def test_minimal(self, mock_emit_event: MagicMock):
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

        mock_emit_event.assert_called_once_with(
            event="prefect.kubernetes.pod.running",
            resource={
                "prefect.resource.id": f"prefect.kubernetes.pod.{pod_id}",
                "prefect.resource.name": "test",
                "kubernetes.namespace": "test",
            },
            id=ANY,
            related=[
                RelatedResource.model_validate(
                    {
                        "prefect.resource.id": f"prefect.flow-run.{flow_run_id}",
                        "prefect.resource.role": "flow-run",
                        "prefect.resource.name": "test",
                    }
                )
            ],
            follows=None,
        )

    async def test_deterministic_event_id(self, mock_emit_event: MagicMock):
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

        first_event_id = mock_emit_event.call_args[1]["id"]
        mock_emit_event.reset_mock()

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

        second_event_id = mock_emit_event.call_args[1]["id"]
        assert first_event_id == second_event_id

    async def test_evicted_pod(self, mock_emit_event: MagicMock):
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

        mock_emit_event.assert_called_once_with(
            event="prefect.kubernetes.pod.evicted",
            resource={
                "prefect.resource.id": f"prefect.kubernetes.pod.{pod_id}",
                "prefect.resource.name": "test",
                "kubernetes.namespace": "test",
                "kubernetes.reason": "OOMKilled",
            },
            id=ANY,
            related=ANY,
            follows=None,
        )

    async def test_all_related_resources(self, mock_emit_event: MagicMock):
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

        mock_emit_event.assert_called_once()
        call_args = mock_emit_event.call_args[1]
        related_resources = call_args["related"]

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

    async def test_event_deduplication(
        self, monkeypatch: pytest.MonkeyPatch, mock_emit_event: MagicMock
    ):
        """Test that checks from existing events when receiving events on startup"""
        mock_client = AsyncMock()
        mock_client.request.return_value = MagicMock(
            json=lambda: {"events": [{"id": "existing-event"}]}
        )

        @asynccontextmanager
        async def mock_get_client():
            try:
                yield mock_client
            finally:
                pass

        monkeypatch.setattr("prefect_kubernetes.observer.get_client", mock_get_client)

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
        mock_emit_event.assert_not_called()

    @pytest.mark.parametrize("phase", ["Pending", "Running", "Succeeded", "Failed"])
    async def test_different_phases(self, mock_emit_event: MagicMock, phase: str):
        """Test handling of different pod phases"""
        pod_id = uuid.uuid4()
        flow_run_id = uuid.uuid4()

        mock_emit_event.reset_mock()
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

        mock_emit_event.assert_called_once()
        call_args = mock_emit_event.call_args[1]
        assert call_args["event"] == f"prefect.kubernetes.pod.{phase.lower()}"


class TestStartAndStopObserver:
    @pytest.mark.timeout(10)
    def test_start_and_stop(self, monkeypatch: pytest.MonkeyPatch):
        """
        Test that the observer can be started and stopped without errors
        and without hanging.
        """
        # Set up a mock to check check for existing pod events
        mock_client = AsyncMock()
        mock_client.request.return_value.json.return_value = {
            "events": [{"id": "existing-event"}]
        }

        @asynccontextmanager
        async def mock_get_client():
            try:
                yield mock_client
            finally:
                pass

        monkeypatch.setattr("prefect_kubernetes.observer.get_client", mock_get_client)

        start_observer()
        sleep(1)
        stop_observer()
