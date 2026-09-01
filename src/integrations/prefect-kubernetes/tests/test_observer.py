import asyncio
import logging
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager
from io import StringIO
from time import sleep
from unittest.mock import AsyncMock, MagicMock, call, patch

import anyio
import pytest
from prefect_kubernetes import observer
from prefect_kubernetes._logging import KopfObjectJsonFormatter
from prefect_kubernetes.diagnostics import diagnose_k8s_pod
from prefect_kubernetes.observer import (
    _ContainerLogEntry,
    _fetch_crashed_pod_logs,
    _mark_flow_run_as_crashed,
    _replicate_pod_event,
    _send_crashed_pod_logs,
    cleanup_fn,
    start_observer,
    stop_observer,
)

from prefect.client.schemas.objects import FlowRun, State
from prefect.events.schemas.events import RelatedResource, Resource
from prefect.exceptions import Abort, ObjectNotFound, Pause
from prefect.types import DateTime


@pytest.fixture(autouse=True)
def reset_observer_lifecycle_state() -> Iterator[None]:
    observer._pod_lifecycle_states.clear()
    yield
    observer._pod_lifecycle_states.clear()


def _pending_event_kwargs(flow_run_id: uuid.UUID, pod_uid: str) -> dict[str, object]:
    return {
        "event": {"type": "MODIFIED"},
        "uid": pod_uid,
        "name": "test",
        "namespace": "test",
        "labels": {
            "prefect.io/flow-run-id": str(flow_run_id),
            "prefect.io/flow-run-name": "test-run",
        },
        "status": {"phase": "Pending"},
        "logger": MagicMock(),
    }


def _unschedulable_status(message: str) -> dict[str, object]:
    return {
        "phase": "Pending",
        "conditions": [
            {
                "type": "PodScheduled",
                "status": "False",
                "reason": "Unschedulable",
                "message": message,
            }
        ],
    }


def _pod_list_response(
    *uids: str | None, continue_token: str | None = None
) -> MagicMock:
    response = MagicMock()
    response.items = [MagicMock(metadata=MagicMock(uid=uid)) for uid in uids]
    response.metadata._continue = continue_token
    return response


@pytest.fixture
def mock_observer_log(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    logger = MagicMock()
    child = MagicMock()
    logger.return_value = child
    child.getChild.return_value = child
    monkeypatch.setattr("prefect_kubernetes.observer.flow_run_logger", logger)
    return child


@pytest.fixture
def pending_state_case(
    mock_orchestration_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[uuid.UUID, AsyncMock]:
    flow_run_id = uuid.uuid4()
    mock_propose = AsyncMock(
        return_value=State(type="PENDING", name="InfrastructurePending")
    )
    monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)
    mock_orchestration_client.read_flow_run.return_value = FlowRun(
        id=flow_run_id,
        name="test-flow-run",
        flow_id=uuid.uuid4(),
        state=State(type="SCHEDULED", name="Scheduled"),
    )
    return flow_run_id, mock_propose


@pytest.fixture
def mock_kubernetes_pod_client(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[MagicMock, MagicMock]:
    api_client = MagicMock(close=AsyncMock())
    core_client = MagicMock()
    monkeypatch.setattr(
        "prefect_kubernetes.observer._get_kubernetes_client",
        AsyncMock(return_value=api_client),
    )
    monkeypatch.setattr(
        "prefect_kubernetes.observer.CoreV1Api",
        MagicMock(return_value=core_client),
    )
    return core_client, api_client


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
    # Initialize the startup event semaphore for tests
    monkeypatch.setattr(
        "prefect_kubernetes.observer._startup_event_semaphore",
        asyncio.Semaphore(5),
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

    @pytest.mark.parametrize(
        "event,status,expected_event,expected_occurred",
        [
            (
                {
                    "type": "ADDED",
                    "object": {
                        "metadata": {"creationTimestamp": "2026-05-11T09:30:00Z"}
                    },
                },
                {"phase": "Pending"},
                "prefect.kubernetes.pod.pending",
                "2026-05-11T09:30:00+00:00",
            ),
            (
                {
                    "type": "MODIFIED",
                    "object": {
                        "metadata": {"creationTimestamp": "2026-05-11T09:29:55Z"}
                    },
                },
                {
                    "phase": "Running",
                    "startTime": "2026-05-11T09:30:01Z",
                    "containerStatuses": [
                        {
                            "name": "main",
                            "state": {"running": {"startedAt": "2026-05-11T09:30:07Z"}},
                        }
                    ],
                },
                "prefect.kubernetes.pod.running",
                "2026-05-11T09:30:07+00:00",
            ),
            (
                {"type": "MODIFIED"},
                {
                    "phase": "Running",
                    "startTime": "2026-05-11T09:30:01Z",
                    "initContainerStatuses": [
                        {
                            "name": "native-sidecar",
                            "state": {"running": {"startedAt": "2026-05-11T09:29:59Z"}},
                        }
                    ],
                    "containerStatuses": [
                        {
                            "name": "main",
                            "state": {"running": {"startedAt": "2026-05-11T09:30:07Z"}},
                        },
                        {
                            "name": "worker",
                            "state": {"running": {"startedAt": "2026-05-11T10:00:00Z"}},
                        },
                    ],
                },
                "prefect.kubernetes.pod.running",
                "2026-05-11T10:00:00+00:00",
            ),
            (
                {"type": "MODIFIED"},
                {"phase": "Running", "startTime": "2026-05-11T09:30:01Z"},
                "prefect.kubernetes.pod.running",
                "2026-05-11T09:30:01+00:00",
            ),
            (
                {"type": "MODIFIED"},
                {
                    "phase": "Succeeded",
                    "containerStatuses": [
                        {
                            "name": "main",
                            "state": {
                                "terminated": {"finishedAt": "2026-05-11T10:00:00Z"}
                            },
                        },
                        {
                            "name": "sidecar",
                            "state": {
                                "terminated": {"finishedAt": "2026-05-11T10:00:05Z"}
                            },
                        },
                    ],
                },
                "prefect.kubernetes.pod.succeeded",
                "2026-05-11T10:00:05+00:00",
            ),
            (
                {"type": "MODIFIED"},
                {
                    "phase": "Failed",
                    "containerStatuses": [
                        {
                            "name": "main",
                            "state": {
                                "terminated": {
                                    "reason": "Evicted",
                                    "finishedAt": "2026-05-11T11:05:49Z",
                                }
                            },
                        }
                    ],
                },
                "prefect.kubernetes.pod.evicted",
                "2026-05-11T11:05:49+00:00",
            ),
        ],
    )
    async def test_uses_kubernetes_timestamp_for_occurred(
        self,
        mock_events_client: AsyncMock,
        event: dict[str, object],
        status: dict[str, object],
        expected_event: str,
        expected_occurred: str,
    ):
        await _replicate_pod_event(
            event=event,
            uid=str(uuid.uuid4()),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(uuid.uuid4()),
                "prefect.io/flow-run-name": "test-run",
            },
            status=status,
            logger=MagicMock(),
        )

        emitted_event = mock_events_client.emit.call_args[1]["event"]
        assert emitted_event.event == expected_event
        assert emitted_event.occurred == DateTime.fromisoformat(expected_occurred)

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
                "containerStatuses": [
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
                "kubernetes.diagnosis": "OOMKilled",
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

    async def test_event_deduplication(
        self, mock_events_client: AsyncMock, mock_orchestration_client: AsyncMock
    ):
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

        # Verify the request was made with correct payload structure
        mock_orchestration_client.request.assert_called_once()
        call_args = mock_orchestration_client.request.call_args
        assert call_args[0] == ("POST", "/events/filter")

        # Verify the json payload has the correct structure: {"filter": {...}}
        json_payload = call_args[1]["json"]
        assert "filter" in json_payload, "Expected 'filter' key in json payload"

        # Verify the nested filter contains expected fields
        event_filter = json_payload["filter"]
        assert "event" in event_filter, "Expected 'event' field in filter"
        assert "resource" in event_filter, "Expected 'resource' field in filter"
        assert "occurred" in event_filter, "Expected 'occurred' field in filter"

        # Verify no event was emitted since one already existed
        mock_events_client.emit.assert_not_called()

    async def test_existing_startup_event_reconciles_lifecycle_state(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Startup deduplication still observes recovery from retained work."""
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        mock_propose = AsyncMock(
            return_value=State(type="PENDING", name="InfrastructurePending")
        )
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)
        mock_orchestration_client.read_flow_run.return_value = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="SCHEDULED", name="Scheduled"),
        )
        mock_logger = MagicMock()
        mock_child = MagicMock()
        mock_logger.return_value = mock_child
        mock_child.getChild.return_value = mock_child
        monkeypatch.setattr("prefect_kubernetes.observer.flow_run_logger", mock_logger)
        kwargs = _pending_event_kwargs(flow_run_id, pod_uid)
        kwargs["status"] = _unschedulable_status(
            "0/1 nodes are available: 1 Insufficient cpu."
        )

        await _replicate_pod_event(**kwargs)
        await _replicate_pod_event(
            event={"type": None},
            uid=pod_uid,
            name="test",
            namespace="test",
            labels=kwargs["labels"],
            status={"phase": "Running"},
            logger=MagicMock(),
        )
        await _replicate_pod_event(**kwargs)

        assert mock_orchestration_client.read_flow_run.call_count == 2
        assert mock_propose.call_count == 2
        assert mock_child.log.call_count == 2

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

    async def test_pending_pod_proposes_infrastructure_pending(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test that a Pending pod proposes InfrastructurePending state."""
        flow_run_id = uuid.uuid4()
        mock_propose = AsyncMock(
            return_value=State(type="PENDING", name="InfrastructurePending")
        )
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        mock_orchestration_client.read_flow_run.return_value = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="PENDING", name="Scheduled"),
        )

        await _replicate_pod_event(
            event={"type": "ADDED"},
            uid=str(uuid.uuid4()),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(flow_run_id),
                "prefect.io/flow-run-name": "test-run",
            },
            status={"phase": "Pending"},
            logger=MagicMock(),
        )

        mock_propose.assert_called_once()
        call_kwargs = mock_propose.call_args[1]
        assert call_kwargs["flow_run_id"] == flow_run_id
        assert call_kwargs["state"].name == "InfrastructurePending"
        assert "pending" in call_kwargs["state"].message.lower()

    async def test_running_pod_does_not_propose_infrastructure_pending(
        self,
        mock_events_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test that a Running pod does not propose InfrastructurePending."""
        mock_propose = AsyncMock()
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=str(uuid.uuid4()),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(uuid.uuid4()),
                "prefect.io/flow-run-name": "test-run",
            },
            status={"phase": "Running"},
            logger=MagicMock(),
        )

        mock_propose.assert_not_called()

    @pytest.mark.parametrize(
        "state_type,state_name",
        [
            ("RUNNING", "Running"),
            ("COMPLETED", "Completed"),
            ("CRASHED", "Crashed"),
            ("PAUSED", "Suspended"),
            ("CANCELLING", "Cancelling"),
            ("PENDING", "InfrastructurePending"),
        ],
    )
    async def test_skips_infrastructure_pending_when_flow_run_already_advanced(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
        state_type: str,
        state_name: str,
    ):
        """Test that InfrastructurePending is not proposed when the flow run
        is already running, final, or paused."""
        flow_run_id = uuid.uuid4()
        mock_propose = AsyncMock()
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        mock_orchestration_client.read_flow_run.return_value = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type=state_type, name=state_name),
        )

        await _replicate_pod_event(
            event={"type": "ADDED"},
            uid=str(uuid.uuid4()),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(flow_run_id),
                "prefect.io/flow-run-name": "test-run",
            },
            status={"phase": "Pending"},
            logger=MagicMock(),
        )

        mock_propose.assert_not_called()

    async def test_skips_infrastructure_pending_when_flow_run_not_found(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test that InfrastructurePending is not proposed when the flow run
        does not exist."""
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        mock_propose = AsyncMock()
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        mock_orchestration_client.read_flow_run.side_effect = ObjectNotFound(
            "Flow run not found"
        )

        await _replicate_pod_event(
            event={"type": "ADDED"},
            uid=pod_uid,
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(flow_run_id),
                "prefect.io/flow-run-name": "test-run",
            },
            status={"phase": "Pending"},
            logger=MagicMock(),
        )

        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=pod_uid,
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(flow_run_id),
                "prefect.io/flow-run-name": "test-run",
            },
            status={"phase": "Pending"},
            logger=MagicMock(),
        )

        mock_propose.assert_not_called()
        assert mock_orchestration_client.read_flow_run.call_count == 1

    async def test_pending_state_check_deduplicates_repeated_events(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Repeated Pending events don't repeat the state lookup and proposal."""
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        mock_propose = AsyncMock(
            return_value=State(type="PENDING", name="InfrastructurePending")
        )
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        mock_orchestration_client.read_flow_run.return_value = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="SCHEDULED", name="Scheduled"),
        )

        for _ in range(2):
            await _replicate_pod_event(
                event={"type": "MODIFIED"},
                uid=pod_uid,
                name="test",
                namespace="test",
                labels={
                    "prefect.io/flow-run-id": str(flow_run_id),
                    "prefect.io/flow-run-name": "test-run",
                },
                status={"phase": "Pending"},
                logger=MagicMock(),
            )

        assert mock_orchestration_client.read_flow_run.call_count == 1
        assert mock_propose.call_count == 1

    async def test_pod_lifecycle_state_survives_more_than_100_000_other_pods(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_observer_log: MagicMock,
        pending_state_case: tuple[uuid.UUID, AsyncMock],
    ):
        """A live pod retains all deduplication state for its lifecycle."""
        flow_run_id, mock_propose = pending_state_case
        pod_uid = str(uuid.uuid4())
        kwargs = _pending_event_kwargs(flow_run_id, pod_uid)
        kwargs["status"] = _unschedulable_status(
            "0/1 nodes are available: 1 Insufficient cpu."
        )

        await _replicate_pod_event(**kwargs)
        for index in range(100_001):
            other_uid = f"other-pod-{index}"
            observer._pod_lifecycle_states.mark_state_check_completed(other_uid)
            observer._pod_lifecycle_states.mark_diagnosis_logged(other_uid, ("other",))
        await _replicate_pod_event(**kwargs)

        mock_orchestration_client.read_flow_run.assert_awaited_once_with(
            flow_run_id=flow_run_id
        )
        mock_propose.assert_awaited_once()
        assert mock_observer_log.log.call_count == 1

    async def test_reconciliation_reenables_absent_pending_pod(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_observer_log: MagicMock,
        pending_state_case: tuple[uuid.UUID, AsyncMock],
        mock_kubernetes_pod_client: tuple[MagicMock, MagicMock],
    ):
        """A complete pod listing releases state for a missed deletion."""
        flow_run_id, mock_propose = pending_state_case
        pod_uid = str(uuid.uuid4())
        kwargs = _pending_event_kwargs(flow_run_id, pod_uid)
        kwargs["status"] = _unschedulable_status(
            "0/1 nodes are available: 1 Insufficient cpu."
        )

        core_client, _ = mock_kubernetes_pod_client
        core_client.list_pod_for_all_namespaces = AsyncMock(
            return_value=_pod_list_response()
        )

        await _replicate_pod_event(**kwargs)
        await observer._reconcile_pod_lifecycle_states(logger=MagicMock())
        await _replicate_pod_event(**kwargs)

        assert mock_orchestration_client.read_flow_run.call_count == 2
        assert mock_propose.call_count == 2
        assert mock_observer_log.log.call_count == 2

    async def test_reconciliation_retains_pod_in_any_observed_namespace(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_observer_log: MagicMock,
        pending_state_case: tuple[uuid.UUID, AsyncMock],
        mock_kubernetes_pod_client: tuple[MagicMock, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ):
        """A complete namespaced listing never releases a live pod."""
        flow_run_id, mock_propose = pending_state_case
        pod_uid = str(uuid.uuid4())
        kwargs = _pending_event_kwargs(flow_run_id, pod_uid)
        kwargs["status"] = _unschedulable_status(
            "0/1 nodes are available: 1 Insufficient cpu."
        )

        core_client, _ = mock_kubernetes_pod_client
        core_client.list_pod_for_all_namespaces = AsyncMock(
            return_value=_pod_list_response()
        )
        core_client.list_namespaced_pod = AsyncMock(
            side_effect=[_pod_list_response(), _pod_list_response(pod_uid)]
        )
        monkeypatch.setattr(observer.settings.observer, "namespaces", {"z", "a"})
        monkeypatch.setattr(
            observer.settings.observer, "additional_label_filters", {"team": "data"}
        )

        await _replicate_pod_event(**kwargs)
        await observer._reconcile_pod_lifecycle_states(logger=MagicMock())
        await _replicate_pod_event(**kwargs)

        assert core_client.list_namespaced_pod.await_args_list == [
            call(
                namespace="a",
                label_selector="prefect.io/flow-run-id,team=data",
                limit=500,
            ),
            call(
                namespace="z",
                label_selector="prefect.io/flow-run-id,team=data",
                limit=500,
            ),
        ]
        core_client.list_pod_for_all_namespaces.assert_not_awaited()
        assert mock_orchestration_client.read_flow_run.call_count == 1
        assert mock_propose.call_count == 1
        assert mock_observer_log.log.call_count == 1

    async def test_reconciliation_follows_all_pages_before_pruning(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_observer_log: MagicMock,
        pending_state_case: tuple[uuid.UUID, AsyncMock],
        mock_kubernetes_pod_client: tuple[MagicMock, MagicMock],
    ):
        """A pod found on a later page remains deduplicated."""
        flow_run_id, mock_propose = pending_state_case
        pod_uid = str(uuid.uuid4())
        kwargs = _pending_event_kwargs(flow_run_id, pod_uid)
        kwargs["status"] = _unschedulable_status(
            "0/1 nodes are available: 1 Insufficient cpu."
        )

        core_client, _ = mock_kubernetes_pod_client
        core_client.list_pod_for_all_namespaces = AsyncMock(
            side_effect=[
                _pod_list_response(continue_token="next-page"),
                _pod_list_response(pod_uid),
            ]
        )
        await _replicate_pod_event(**kwargs)
        await observer._reconcile_pod_lifecycle_states(logger=MagicMock())
        await _replicate_pod_event(**kwargs)

        assert core_client.list_pod_for_all_namespaces.await_args_list == [
            call(label_selector="prefect.io/flow-run-id", limit=500),
            call(
                label_selector="prefect.io/flow-run-id",
                limit=500,
                _continue="next-page",
            ),
        ]
        assert mock_orchestration_client.read_flow_run.call_count == 1
        assert mock_propose.call_count == 1
        assert mock_observer_log.log.call_count == 1

    async def test_reconciliation_keeps_state_for_incomplete_pod_data(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_observer_log: MagicMock,
        pending_state_case: tuple[uuid.UUID, AsyncMock],
        mock_kubernetes_pod_client: tuple[MagicMock, MagicMock],
    ):
        """A listing without an object UID cannot prove that a pod is absent."""
        flow_run_id, mock_propose = pending_state_case
        pod_uid = str(uuid.uuid4())
        kwargs = _pending_event_kwargs(flow_run_id, pod_uid)
        kwargs["status"] = _unschedulable_status(
            "0/1 nodes are available: 1 Insufficient cpu."
        )
        core_client, _ = mock_kubernetes_pod_client
        core_client.list_pod_for_all_namespaces = AsyncMock(
            return_value=_pod_list_response(None)
        )

        await _replicate_pod_event(**kwargs)
        with pytest.raises(RuntimeError, match="missing a UID"):
            await observer._reconcile_pod_lifecycle_states(logger=MagicMock())
        await _replicate_pod_event(**kwargs)

        assert mock_orchestration_client.read_flow_run.call_count == 1
        assert mock_propose.call_count == 1
        assert mock_observer_log.log.call_count == 1

    async def test_reconciliation_does_not_prune_after_partial_failure(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_observer_log: MagicMock,
        pending_state_case: tuple[uuid.UUID, AsyncMock],
        mock_kubernetes_pod_client: tuple[MagicMock, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Every configured namespace must be listed before state is released."""
        flow_run_id, mock_propose = pending_state_case
        pod_uid = str(uuid.uuid4())
        kwargs = _pending_event_kwargs(flow_run_id, pod_uid)
        kwargs["status"] = _unschedulable_status(
            "0/1 nodes are available: 1 Insufficient cpu."
        )
        core_client, _ = mock_kubernetes_pod_client
        core_client.list_namespaced_pod = AsyncMock(
            side_effect=[_pod_list_response(), RuntimeError("namespace unavailable")]
        )
        monkeypatch.setattr(observer.settings.observer, "namespaces", {"a", "z"})

        await _replicate_pod_event(**kwargs)
        with pytest.raises(RuntimeError, match="namespace unavailable"):
            await observer._reconcile_pod_lifecycle_states(logger=MagicMock())
        await _replicate_pod_event(**kwargs)

        assert mock_orchestration_client.read_flow_run.call_count == 1
        assert mock_propose.call_count == 1
        assert mock_observer_log.log.call_count == 1

    async def test_reconciliation_preserves_state_added_during_listing(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_observer_log: MagicMock,
        pending_state_case: tuple[uuid.UUID, AsyncMock],
        mock_kubernetes_pod_client: tuple[MagicMock, MagicMock],
    ):
        """A concurrent pod event cannot be invalidated by an older snapshot."""
        flow_run_id, mock_propose = pending_state_case
        old_kwargs = _pending_event_kwargs(flow_run_id, str(uuid.uuid4()))
        old_kwargs["status"] = _unschedulable_status(
            "0/1 nodes are available: 1 Insufficient cpu."
        )
        new_kwargs = _pending_event_kwargs(flow_run_id, str(uuid.uuid4()))
        new_kwargs["status"] = old_kwargs["status"]
        core_client, _ = mock_kubernetes_pod_client

        async def list_while_new_pod_is_processed(**_: object) -> MagicMock:
            await _replicate_pod_event(**new_kwargs)
            return _pod_list_response()

        core_client.list_pod_for_all_namespaces = AsyncMock(
            side_effect=list_while_new_pod_is_processed
        )

        await _replicate_pod_event(**old_kwargs)
        await observer._reconcile_pod_lifecycle_states(logger=MagicMock())
        await _replicate_pod_event(**new_kwargs)

        assert mock_orchestration_client.read_flow_run.call_count == 2
        assert mock_propose.call_count == 2
        assert mock_observer_log.log.call_count == 2

    async def test_reconciliation_preserves_state_touched_during_listing(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_observer_log: MagicMock,
        pending_state_case: tuple[uuid.UUID, AsyncMock],
        mock_kubernetes_pod_client: tuple[MagicMock, MagicMock],
    ):
        """A concurrent event protects an existing UID from a stale listing."""
        flow_run_id, mock_propose = pending_state_case
        kwargs = _pending_event_kwargs(flow_run_id, str(uuid.uuid4()))
        kwargs["status"] = _unschedulable_status(
            "0/1 nodes are available: 1 Insufficient cpu."
        )
        core_client, _ = mock_kubernetes_pod_client

        async def list_while_pod_is_observed_again(**_: object) -> MagicMock:
            await _replicate_pod_event(**kwargs)
            return _pod_list_response()

        core_client.list_pod_for_all_namespaces = AsyncMock(
            side_effect=list_while_pod_is_observed_again
        )

        await _replicate_pod_event(**kwargs)
        await observer._reconcile_pod_lifecycle_states(logger=MagicMock())
        await _replicate_pod_event(**kwargs)

        assert mock_orchestration_client.read_flow_run.call_count == 1
        assert mock_propose.call_count == 1
        assert mock_observer_log.log.call_count == 1

    async def test_overlapping_reconciliations_keep_touch_tracking_isolated(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_observer_log: MagicMock,
        pending_state_case: tuple[uuid.UUID, AsyncMock],
        mock_kubernetes_pod_client: tuple[MagicMock, MagicMock],
    ):
        """A finishing pass cannot unregister another pass's touch tracking."""
        flow_run_id, mock_propose = pending_state_case
        pod_uid = str(uuid.uuid4())
        kwargs = _pending_event_kwargs(flow_run_id, pod_uid)
        kwargs["status"] = _unschedulable_status(
            "0/1 nodes are available: 1 Insufficient cpu."
        )
        first_started = asyncio.Event()
        finish_first = asyncio.Event()
        list_count = 0
        core_client, _ = mock_kubernetes_pod_client

        async def list_in_reverse_completion_order(**_: object) -> MagicMock:
            nonlocal list_count
            list_count += 1
            if list_count == 1:
                first_started.set()
                await finish_first.wait()
                return _pod_list_response()
            return _pod_list_response(pod_uid)

        core_client.list_pod_for_all_namespaces = AsyncMock(
            side_effect=list_in_reverse_completion_order
        )

        await _replicate_pod_event(**kwargs)
        first = asyncio.create_task(
            observer._reconcile_pod_lifecycle_states(logger=MagicMock())
        )
        await asyncio.wait_for(first_started.wait(), timeout=1)
        await observer._reconcile_pod_lifecycle_states(logger=MagicMock())
        await _replicate_pod_event(**kwargs)
        finish_first.set()
        await asyncio.wait_for(first, timeout=1)
        await _replicate_pod_event(**kwargs)

        assert mock_orchestration_client.read_flow_run.call_count == 1
        assert mock_propose.call_count == 1
        assert mock_observer_log.log.call_count == 1

    async def test_reconciliation_cancellation_survives_client_close_failure(
        self,
        mock_events_client: AsyncMock,
        pending_state_case: tuple[uuid.UUID, AsyncMock],
        mock_kubernetes_pod_client: tuple[MagicMock, MagicMock],
    ):
        """A client close failure cannot replace reconciliation cancellation."""
        flow_run_id, _ = pending_state_case
        started = asyncio.Event()
        core_client, api_client = mock_kubernetes_pod_client

        async def blocking_list(**_: object) -> MagicMock:
            started.set()
            await asyncio.Future()
            raise AssertionError("unreachable")

        core_client.list_pod_for_all_namespaces = AsyncMock(side_effect=blocking_list)
        api_client.close.side_effect = RuntimeError("client close failed")
        await _replicate_pod_event(
            **_pending_event_kwargs(flow_run_id, str(uuid.uuid4()))
        )

        reconciliation = asyncio.create_task(
            observer._reconcile_pod_lifecycle_states(logger=MagicMock())
        )
        await asyncio.wait_for(started.wait(), timeout=1)
        reconciliation.cancel()

        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(reconciliation, timeout=1)
        api_client.close.assert_awaited_once()

    async def test_completed_state_check_deduplicates_when_flow_run_already_advanced(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """A completed check that requires no proposal is also deduplicated."""
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        mock_propose = AsyncMock()
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        mock_orchestration_client.read_flow_run.return_value = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="RUNNING", name="Running"),
        )

        for _ in range(2):
            await _replicate_pod_event(
                event={"type": "MODIFIED"},
                uid=pod_uid,
                name="test",
                namespace="test",
                labels={
                    "prefect.io/flow-run-id": str(flow_run_id),
                    "prefect.io/flow-run-name": "test-run",
                },
                status={"phase": "Pending"},
                logger=MagicMock(),
            )

        assert mock_orchestration_client.read_flow_run.call_count == 1
        mock_propose.assert_not_called()

    async def test_pending_state_check_retried_after_failure(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """A failed state check is retried on the next event."""
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        mock_propose = AsyncMock()
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        mock_orchestration_client.read_flow_run.side_effect = Exception("boom")

        for _ in range(2):
            await _replicate_pod_event(
                event={"type": "MODIFIED"},
                uid=pod_uid,
                name="test",
                namespace="test",
                labels={
                    "prefect.io/flow-run-id": str(flow_run_id),
                    "prefect.io/flow-run-name": "test-run",
                },
                status={"phase": "Pending"},
                logger=MagicMock(),
            )

        assert mock_orchestration_client.read_flow_run.call_count == 2

    async def test_pending_state_check_retried_after_timeout(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """A timed-out proposal is retried on the next event."""
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())

        real_move_on_after = anyio.move_on_after
        monkeypatch.setattr(
            "prefect_kubernetes.observer.anyio.move_on_after",
            lambda seconds: real_move_on_after(0.01),
        )

        async def slow_propose(**kwargs):
            await anyio.sleep(5)

        mock_propose = AsyncMock(side_effect=slow_propose)
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        mock_orchestration_client.read_flow_run.return_value = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="SCHEDULED", name="Scheduled"),
        )

        for _ in range(2):
            await _replicate_pod_event(
                event={"type": "MODIFIED"},
                uid=pod_uid,
                name="test",
                namespace="test",
                labels={
                    "prefect.io/flow-run-id": str(flow_run_id),
                    "prefect.io/flow-run-name": "test-run",
                },
                status={"phase": "Pending"},
                logger=MagicMock(),
            )

        assert mock_propose.call_count == 2

    @pytest.mark.parametrize(
        ("replacement_type", "replacement_name"),
        [("SCHEDULED", "Scheduled"), ("PENDING", "Pending")],
    )
    async def test_rejected_proposal_retried(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
        replacement_type: str,
        replacement_name: str,
    ):
        """A rejected proposal is retried on the next pod event."""
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        mock_propose = AsyncMock(
            return_value=State(type=replacement_type, name=replacement_name)
        )
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        mock_orchestration_client.read_flow_run.return_value = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="SCHEDULED", name="Scheduled"),
        )

        for _ in range(2):
            await _replicate_pod_event(**_pending_event_kwargs(flow_run_id, pod_uid))

        assert mock_orchestration_client.read_flow_run.call_count == 2
        assert mock_propose.call_count == 2

    async def test_paused_proposal_completes_state_check(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """A paused proposal completes the state check for repeated events."""
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        mock_propose = AsyncMock(
            side_effect=Pause(state=State(type="PAUSED", name="Paused"))
        )
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        mock_orchestration_client.read_flow_run.return_value = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="SCHEDULED", name="Scheduled"),
        )

        for _ in range(2):
            await _replicate_pod_event(
                event={"type": "MODIFIED"},
                uid=pod_uid,
                name="test",
                namespace="test",
                labels={
                    "prefect.io/flow-run-id": str(flow_run_id),
                    "prefect.io/flow-run-name": "test-run",
                },
                status={"phase": "Pending"},
                logger=MagicMock(),
            )

        assert mock_orchestration_client.read_flow_run.call_count == 1
        assert mock_propose.call_count == 1

    async def test_deleted_pod_reenables_lifecycle_processing(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_observer_log: MagicMock,
        pending_state_case: tuple[uuid.UUID, AsyncMock],
    ):
        """A deleted pod can repeat its state check and diagnosis if it reappears."""
        flow_run_id, mock_propose = pending_state_case
        kwargs = _pending_event_kwargs(flow_run_id, str(uuid.uuid4()))
        kwargs["status"] = _unschedulable_status(
            "0/1 nodes are available: 1 Insufficient cpu."
        )

        await _replicate_pod_event(**kwargs)
        await _replicate_pod_event(**{**kwargs, "event": {"type": "DELETED"}})
        await _replicate_pod_event(**kwargs)

        assert mock_orchestration_client.read_flow_run.call_count == 2
        assert mock_propose.call_count == 2
        assert mock_observer_log.log.call_count == 2

    @pytest.mark.parametrize("failure_stage", ["emit", "diagnose"])
    async def test_deleted_pod_reenables_processing_after_handler_failure(
        self,
        failure_stage: str,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_observer_log: MagicMock,
        pending_state_case: tuple[uuid.UUID, AsyncMock],
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Deletion owns lifecycle cleanup regardless of the failing handler step."""
        flow_run_id, mock_propose = pending_state_case
        kwargs = _pending_event_kwargs(flow_run_id, str(uuid.uuid4()))
        kwargs["status"] = _unschedulable_status(
            "0/1 nodes are available: 1 Insufficient cpu."
        )
        await _replicate_pod_event(**kwargs)

        if failure_stage == "emit":
            mock_events_client.emit.side_effect = RuntimeError(
                "event service unavailable"
            )
            error = "event service unavailable"
        else:
            monkeypatch.setattr(
                "prefect_kubernetes.observer.diagnose_k8s_pod",
                MagicMock(side_effect=RuntimeError("diagnosis failed")),
            )
            error = "diagnosis failed"

        with pytest.raises(RuntimeError, match=error):
            await _replicate_pod_event(**{**kwargs, "event": {"type": "DELETED"}})

        mock_events_client.emit.side_effect = None
        monkeypatch.setattr(
            "prefect_kubernetes.observer.diagnose_k8s_pod", diagnose_k8s_pod
        )
        await _replicate_pod_event(**kwargs)

        assert mock_orchestration_client.read_flow_run.call_count == 2
        assert mock_propose.call_count == 2
        assert mock_observer_log.log.call_count == 2

    async def test_cleanup_reenables_lifecycle_processing(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_observer_log: MagicMock,
        pending_state_case: tuple[uuid.UUID, AsyncMock],
    ):
        """Observer shutdown releases all pod-owned deduplication state."""
        flow_run_id, mock_propose = pending_state_case
        kwargs = _pending_event_kwargs(flow_run_id, str(uuid.uuid4()))
        kwargs["status"] = _unschedulable_status(
            "0/1 nodes are available: 1 Insufficient cpu."
        )

        await _replicate_pod_event(**kwargs)
        await cleanup_fn(logger=MagicMock())
        await _replicate_pod_event(**kwargs)

        assert mock_orchestration_client.read_flow_run.call_count == 2
        assert mock_propose.call_count == 2
        assert mock_observer_log.log.call_count == 2

    async def test_observer_lifecycle_owns_reconciliation_task(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Observer cleanup cancels and awaits the reconciliation loop."""
        started = asyncio.Event()
        stopped = asyncio.Event()

        async def reconciliation_loop(logger: logging.Logger) -> None:
            started.set()
            try:
                await asyncio.Future()
            finally:
                stopped.set()

        monkeypatch.setattr(
            observer,
            "_periodically_reconcile_pod_lifecycle_states",
            reconciliation_loop,
        )

        await observer.initialize_clients(logger=MagicMock())
        await asyncio.wait_for(started.wait(), timeout=1)
        await cleanup_fn(logger=MagicMock())

        assert stopped.is_set()

    async def test_cleanup_reenables_lifecycle_processing_if_client_cleanup_fails(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_observer_log: MagicMock,
        pending_state_case: tuple[uuid.UUID, AsyncMock],
    ):
        """Lifecycle state is released even when client cleanup fails."""
        flow_run_id, mock_propose = pending_state_case
        kwargs = _pending_event_kwargs(flow_run_id, str(uuid.uuid4()))
        kwargs["status"] = _unschedulable_status(
            "0/1 nodes are available: 1 Insufficient cpu."
        )

        await _replicate_pod_event(**kwargs)
        mock_events_client.__aexit__.side_effect = RuntimeError("events cleanup failed")

        with pytest.raises(RuntimeError, match="events cleanup failed"):
            await cleanup_fn(logger=MagicMock())

        mock_events_client.__aexit__.side_effect = None
        await _replicate_pod_event(**kwargs)

        assert mock_orchestration_client.read_flow_run.call_count == 2
        assert mock_propose.call_count == 2
        assert mock_observer_log.log.call_count == 2

    async def test_reconciliation_task_failure_does_not_skip_client_cleanup(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """A reconciliation failure cannot prevent normal client cleanup."""

        async def fail_reconciliation() -> None:
            raise RuntimeError("reconciliation failed")

        task = asyncio.create_task(fail_reconciliation())
        await asyncio.sleep(0)
        monkeypatch.setattr(observer, "_pod_lifecycle_reconciliation_task", task)

        with pytest.raises(RuntimeError, match="reconciliation failed"):
            await cleanup_fn(logger=MagicMock())

        mock_events_client.__aexit__.assert_awaited_once_with(None, None, None)
        mock_orchestration_client.__aexit__.assert_awaited_once_with(None, None, None)

    async def test_pending_state_check_reenabled_on_phase_change(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """The completed state check is dropped when the pod leaves Pending."""
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        mock_propose = AsyncMock(
            return_value=State(type="PENDING", name="InfrastructurePending")
        )
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        mock_orchestration_client.read_flow_run.return_value = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="SCHEDULED", name="Scheduled"),
        )

        labels = {
            "prefect.io/flow-run-id": str(flow_run_id),
            "prefect.io/flow-run-name": "test-run",
        }

        await _replicate_pod_event(**_pending_event_kwargs(flow_run_id, pod_uid))

        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=pod_uid,
            name="test",
            namespace="test",
            labels=labels,
            status={"phase": "Running"},
            logger=MagicMock(),
        )

        await _replicate_pod_event(**_pending_event_kwargs(flow_run_id, pod_uid))

        assert mock_orchestration_client.read_flow_run.call_count == 2
        assert mock_propose.call_count == 2

    async def test_diagnosis_emits_flow_run_log_for_oom(
        self,
        mock_events_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test that OOMKilled diagnosis emits a flow run log."""
        flow_run_id = uuid.uuid4()
        mock_logger = MagicMock()
        mock_child = MagicMock()
        mock_logger.return_value = mock_child
        mock_child.getChild.return_value = mock_child
        monkeypatch.setattr("prefect_kubernetes.observer.flow_run_logger", mock_logger)

        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=str(uuid.uuid4()),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(flow_run_id),
                "prefect.io/flow-run-name": "test-run",
            },
            status={
                "phase": "Failed",
                "containerStatuses": [
                    {
                        "name": "main",
                        "state": {
                            "terminated": {
                                "reason": "OOMKilled",
                                "exitCode": 137,
                            }
                        },
                    }
                ],
            },
            logger=MagicMock(),
        )

        mock_logger.assert_called_once_with(flow_run_id=flow_run_id)
        mock_child.getChild.assert_called_once_with("observer")
        mock_child.log.assert_called_once()
        log_args = mock_child.log.call_args
        assert log_args[0][0] == logging.ERROR
        assert "OOMKilled" in log_args[0][1] % log_args[0][2:]

    async def test_diagnosis_emits_warning_for_unschedulable(
        self,
        mock_events_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test that Unschedulable diagnosis emits a warning-level flow run log."""
        flow_run_id = uuid.uuid4()
        mock_logger = MagicMock()
        mock_child = MagicMock()
        mock_logger.return_value = mock_child
        mock_child.getChild.return_value = mock_child
        monkeypatch.setattr("prefect_kubernetes.observer.flow_run_logger", mock_logger)

        await _replicate_pod_event(
            event={"type": "ADDED"},
            uid=str(uuid.uuid4()),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(flow_run_id),
                "prefect.io/flow-run-name": "test-run",
            },
            status={
                "phase": "Pending",
                "conditions": [
                    {
                        "type": "PodScheduled",
                        "status": "False",
                        "reason": "Unschedulable",
                        "message": "0/3 nodes are available.",
                    }
                ],
            },
            logger=MagicMock(),
        )

        mock_child.log.assert_called_once()
        assert mock_child.log.call_args[0][0] == logging.WARNING

    async def test_diagnosis_emitted_as_event_label_for_unschedulable(
        self,
        mock_events_client: AsyncMock,
    ):
        """The diagnosis category is emitted as a matchable event label."""
        pod_id = uuid.uuid4()

        await _replicate_pod_event(
            event={"type": "ADDED"},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(uuid.uuid4()),
                "prefect.io/flow-run-name": "test-run",
            },
            status={
                "phase": "Pending",
                "conditions": [
                    {
                        "type": "PodScheduled",
                        "status": "False",
                        "reason": "Unschedulable",
                        "message": "0/3 nodes are available: 3 insufficient cpu.",
                    }
                ],
            },
            logger=MagicMock(),
        )

        emitted_event = mock_events_client.emit.call_args[1]["event"]
        assert (
            emitted_event.resource["kubernetes.diagnosis"]
            == "Unschedulable.InsufficientResources"
        )

    async def test_no_diagnosis_label_for_healthy_pod(
        self,
        mock_events_client: AsyncMock,
    ):
        """Healthy pods carry no diagnosis label on their event."""
        await _replicate_pod_event(
            event={"type": "ADDED"},
            uid=str(uuid.uuid4()),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(uuid.uuid4()),
                "prefect.io/flow-run-name": "test-run",
            },
            status={
                "phase": "Running",
                "containerStatuses": [
                    {
                        "name": "main",
                        "state": {"running": {"startedAt": "2024-01-01T00:00:00Z"}},
                    }
                ],
            },
            logger=MagicMock(),
        )

        emitted_event = mock_events_client.emit.call_args[1]["event"]
        assert "kubernetes.diagnosis" not in emitted_event.resource

    async def test_diagnosis_change_produces_distinct_event_id(
        self,
        mock_events_client: AsyncMock,
    ):
        """A Pending pod that becomes Unschedulable emits a distinct event.

        The diagnosis must participate in the deterministic event ID so the
        diagnosed event is not deduplicated away by the server (which would
        otherwise happen since phase and restart count are unchanged).
        """
        pod_id = uuid.uuid4()
        labels = {
            "prefect.io/flow-run-id": str(uuid.uuid4()),
            "prefect.io/flow-run-name": "test-run",
        }

        await _replicate_pod_event(
            event={"type": "ADDED"},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels=labels,
            status={"phase": "Pending"},
            logger=MagicMock(),
        )
        undiagnosed_id = mock_events_client.emit.call_args[1]["event"].id

        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=str(pod_id),
            name="test",
            namespace="test",
            labels=labels,
            status={
                "phase": "Pending",
                "conditions": [
                    {
                        "type": "PodScheduled",
                        "status": "False",
                        "reason": "Unschedulable",
                        "message": "0/3 nodes are available: 3 insufficient cpu.",
                    }
                ],
            },
            logger=MagicMock(),
        )
        diagnosed_id = mock_events_client.emit.call_args[1]["event"].id

        assert undiagnosed_id != diagnosed_id

    async def test_no_diagnosis_for_healthy_pod(
        self,
        mock_events_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test that healthy pods do not emit diagnosis logs."""
        mock_logger = MagicMock()
        monkeypatch.setattr("prefect_kubernetes.observer.flow_run_logger", mock_logger)

        await _replicate_pod_event(
            event={"type": "ADDED"},
            uid=str(uuid.uuid4()),
            name="test",
            namespace="test",
            labels={
                "prefect.io/flow-run-id": str(uuid.uuid4()),
                "prefect.io/flow-run-name": "test-run",
            },
            status={
                "phase": "Running",
                "containerStatuses": [
                    {
                        "name": "main",
                        "state": {"running": {"startedAt": "2024-01-01T00:00:00Z"}},
                    }
                ],
            },
            logger=MagicMock(),
        )

        mock_logger.assert_not_called()

    async def test_diagnosis_deduplicates_repeated_events(
        self,
        mock_events_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test that the same diagnosis is not logged twice for repeated events."""
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        mock_logger = MagicMock()
        mock_child = MagicMock()
        mock_logger.return_value = mock_child
        mock_child.getChild.return_value = mock_child
        monkeypatch.setattr("prefect_kubernetes.observer.flow_run_logger", mock_logger)

        oom_status = {
            "phase": "Failed",
            "containerStatuses": [
                {
                    "name": "main",
                    "state": {"terminated": {"reason": "OOMKilled", "exitCode": 137}},
                }
            ],
        }
        labels = {
            "prefect.io/flow-run-id": str(flow_run_id),
            "prefect.io/flow-run-name": "test-run",
        }

        # First event: should log
        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=pod_uid,
            name="test",
            namespace="test",
            labels=labels,
            status=oom_status,
            logger=MagicMock(),
        )
        assert mock_child.log.call_count == 1

        # Second event with same diagnosis: should NOT log again
        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=pod_uid,
            name="test",
            namespace="test",
            labels=labels,
            status=oom_status,
            logger=MagicMock(),
        )
        assert mock_child.log.call_count == 1  # still 1

        # Pod recovers (healthy status releases diagnosis state)
        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=pod_uid,
            name="test",
            namespace="test",
            labels=labels,
            status={
                "phase": "Running",
                "containerStatuses": [
                    {
                        "name": "main",
                        "state": {"running": {"startedAt": "2024-01-01T00:00:00Z"}},
                    }
                ],
            },
            logger=MagicMock(),
        )
        assert mock_child.log.call_count == 1  # still 1, no diagnosis for healthy

        # Same failure recurs: should log again
        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=pod_uid,
            name="test",
            namespace="test",
            labels=labels,
            status=oom_status,
            logger=MagicMock(),
        )
        assert mock_child.log.call_count == 2  # logged again after recovery

    async def test_diagnosis_logging_failure_retries_without_suppressing_event(
        self,
        mock_events_client: AsyncMock,
        mock_observer_log: MagicMock,
    ):
        """A failed diagnosis log retries without suppressing pod events."""
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        mock_observer_log.log.side_effect = [RuntimeError("log failed"), None]
        kwargs = {
            "event": {"type": "MODIFIED"},
            "uid": pod_uid,
            "name": "test",
            "namespace": "test",
            "labels": {
                "prefect.io/flow-run-id": str(flow_run_id),
                "prefect.io/flow-run-name": "test-run",
            },
            "status": {
                "phase": "Failed",
                "containerStatuses": [
                    {
                        "name": "main",
                        "state": {
                            "terminated": {"reason": "OOMKilled", "exitCode": 137}
                        },
                    }
                ],
            },
            "logger": MagicMock(),
        }

        await _replicate_pod_event(**kwargs)
        await _replicate_pod_event(**kwargs)

        assert mock_observer_log.log.call_count == 2
        assert mock_events_client.emit.await_count == 2

    @pytest.mark.parametrize(
        ("first_message", "equivalent_message", "changed_message"),
        [
            (
                "0/3 nodes are available: 3 Insufficient cpu.",
                "0/5 nodes are available: 5 Insufficient cpu.",
                "0/5 nodes are available: 5 Insufficient ephemeral-storage.",
            ),
            (
                (
                    "0/1 nodes are available: 1 node declared features check failed "
                    "- unsatisfied requirements: FeatureA, FeatureB."
                ),
                (
                    "0/1 nodes are available: 1 node declared features check failed "
                    "- unsatisfied requirements: FeatureB, FeatureA."
                ),
                (
                    "0/1 nodes are available: 1 node declared features check failed "
                    "- unsatisfied requirements: FeatureA, FeatureC."
                ),
            ),
        ],
        ids=["node-counts", "node-declared-features"],
    )
    async def test_diagnosis_dedup_uses_normalized_scheduler_cause(
        self,
        first_message: str,
        equivalent_message: str,
        changed_message: str,
        mock_events_client: AsyncMock,
        mock_observer_log: MagicMock,
    ):
        """Equivalent scheduler output deduplicates while cause changes log."""
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        kwargs = _pending_event_kwargs(flow_run_id, pod_uid)

        for message in (first_message, equivalent_message):
            kwargs["status"] = _unschedulable_status(message)
            await _replicate_pod_event(**kwargs)
        assert mock_observer_log.log.call_count == 1

        kwargs["status"] = _unschedulable_status(changed_message)
        await _replicate_pod_event(**kwargs)
        assert mock_observer_log.log.call_count == 2

    async def test_diagnosis_logs_distinct_unrecognized_scheduler_messages(
        self,
        mock_events_client: AsyncMock,
        mock_observer_log: MagicMock,
    ):
        """Unsupported scheduler formats retain their exact log identity."""
        flow_run_id = uuid.uuid4()
        kwargs = _pending_event_kwargs(flow_run_id, str(uuid.uuid4()))

        for message in (
            "scheduler v2: 0/3 nodes are available: 3 Insufficient cpu.",
            "scheduler v3: 0/3 nodes are available: 3 Insufficient cpu.",
        ):
            kwargs["status"] = _unschedulable_status(message)
            await _replicate_pod_event(**kwargs)

        assert mock_observer_log.log.call_count == 2

    async def test_startup_event_semaphore_limits_concurrency(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test that startup event deduplication respects semaphore concurrency limit"""
        # Track concurrent requests
        concurrent_count = 0
        max_concurrent = 0
        semaphore_limit = 2

        # Set up a semaphore with a small limit for testing
        monkeypatch.setattr(
            "prefect_kubernetes.observer._startup_event_semaphore",
            asyncio.Semaphore(semaphore_limit),
        )

        # Configure mock to return no existing events so we can track the full request
        json_response = MagicMock()
        json_response.json.return_value = {"events": []}
        mock_orchestration_client.request.return_value = json_response

        async def slow_request(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.1)  # Simulate network delay
            concurrent_count -= 1
            return json_response

        mock_orchestration_client.request.side_effect = slow_request

        # Launch multiple startup events concurrently
        tasks = []
        for i in range(5):
            tasks.append(
                asyncio.create_task(
                    _replicate_pod_event(
                        event={"type": None},
                        uid=str(uuid.uuid4()),
                        name=f"test-{i}",
                        namespace="test",
                        labels={
                            "prefect.io/flow-run-id": str(uuid.uuid4()),
                            "prefect.io/flow-run-name": f"test-run-{i}",
                        },
                        status={"phase": "Running"},
                        logger=MagicMock(),
                    )
                )
            )

        await asyncio.gather(*tasks)

        # Verify the semaphore limited concurrency
        assert max_concurrent <= semaphore_limit, (
            f"Expected max {semaphore_limit} concurrent requests, but got {max_concurrent}"
        )
        # Verify all requests were eventually made
        assert mock_orchestration_client.request.call_count == 5


class TestPodLifecycleDiagnosis:
    """Integration-style tests that exercise full pod lifecycle scenarios
    through _replicate_pod_event, verifying the interplay between event
    emission, state proposals, and diagnosis logging."""

    async def test_pending_to_image_pull_failure_lifecycle(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Simulate a pod that starts Pending, then fails with ImagePullBackOff.

        Verifies:
        - Pending phase proposes InfrastructurePending
        - ImagePullBackOff emits an ERROR-level flow run log
        - Both phases emit the correct Prefect events
        """
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        mock_propose = AsyncMock(
            return_value=State(type="PENDING", name="InfrastructurePending")
        )
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)
        mock_fr_logger = MagicMock()
        mock_fr_child = MagicMock()
        mock_fr_logger.return_value = mock_fr_child
        mock_fr_child.getChild.return_value = mock_fr_child
        monkeypatch.setattr(
            "prefect_kubernetes.observer.flow_run_logger", mock_fr_logger
        )

        mock_orchestration_client.read_flow_run.return_value = FlowRun(
            id=flow_run_id,
            name="my-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="PENDING", name="Scheduled"),
        )

        base_labels = {
            "prefect.io/flow-run-id": str(flow_run_id),
            "prefect.io/flow-run-name": "my-flow-run",
        }

        # Step 1: Pod is Pending (no issues yet)
        await _replicate_pod_event(
            event={"type": "ADDED"},
            uid=pod_uid,
            name="test-pod",
            namespace="default",
            labels=base_labels,
            status={"phase": "Pending"},
            logger=MagicMock(),
        )

        # InfrastructurePending should be proposed
        assert mock_propose.call_count == 1
        assert mock_propose.call_args[1]["state"].name == "InfrastructurePending"
        # No diagnosis log for a clean Pending pod
        mock_fr_logger.assert_not_called()
        # Event should be emitted
        assert mock_events_client.emit.call_count == 1
        assert (
            mock_events_client.emit.call_args[1]["event"].event
            == "prefect.kubernetes.pod.pending"
        )

        mock_propose.reset_mock()
        mock_events_client.emit.reset_mock()

        # After proposal succeeds, the flow run is now InfrastructurePending
        mock_orchestration_client.read_flow_run.return_value = FlowRun(
            id=flow_run_id,
            name="my-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="PENDING", name="InfrastructurePending"),
        )

        # Step 2: Pod is still Pending but now has ImagePullBackOff
        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=pod_uid,
            name="test-pod",
            namespace="default",
            labels=base_labels,
            status={
                "phase": "Pending",
                "containerStatuses": [
                    {
                        "name": "flow-container",
                        "state": {
                            "waiting": {
                                "reason": "ImagePullBackOff",
                                "message": "Back-off pulling image",
                            }
                        },
                    }
                ],
            },
            logger=MagicMock(),
        )

        # InfrastructurePending already set, so no re-proposal
        mock_propose.assert_not_called()
        # Diagnosis log should now be emitted at ERROR level
        mock_fr_logger.assert_called_once_with(flow_run_id=flow_run_id)
        mock_fr_child.log.assert_called_once()
        assert mock_fr_child.log.call_args[0][0] == logging.ERROR
        assert (
            "flow-container"
            in mock_fr_child.log.call_args[0][1] % (mock_fr_child.log.call_args[0][2:])
        )

    async def test_pending_unschedulable_to_running_lifecycle(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Simulate a pod that is Pending+Unschedulable, then transitions to Running.

        Verifies:
        - Unschedulable emits a WARNING-level diagnosis log
        - Running phase does not propose InfrastructurePending or emit diagnosis
        """
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        mock_propose = AsyncMock(
            return_value=State(type="PENDING", name="InfrastructurePending")
        )
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)
        mock_fr_logger = MagicMock()
        mock_fr_child = MagicMock()
        mock_fr_logger.return_value = mock_fr_child
        mock_fr_child.getChild.return_value = mock_fr_child
        monkeypatch.setattr(
            "prefect_kubernetes.observer.flow_run_logger", mock_fr_logger
        )

        mock_orchestration_client.read_flow_run.return_value = FlowRun(
            id=flow_run_id,
            name="my-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="PENDING", name="Scheduled"),
        )

        base_labels = {
            "prefect.io/flow-run-id": str(flow_run_id),
            "prefect.io/flow-run-name": "my-flow-run",
        }

        # Step 1: Pod is Pending and Unschedulable
        await _replicate_pod_event(
            event={"type": "ADDED"},
            uid=pod_uid,
            name="test-pod",
            namespace="default",
            labels=base_labels,
            status={
                "phase": "Pending",
                "conditions": [
                    {
                        "type": "PodScheduled",
                        "status": "False",
                        "reason": "Unschedulable",
                        "message": "0/3 nodes are available: insufficient memory.",
                    }
                ],
            },
            logger=MagicMock(),
        )

        assert mock_propose.call_count == 1
        assert mock_propose.call_args[1]["state"].name == "InfrastructurePending"
        mock_fr_child.log.assert_called_once()
        assert mock_fr_child.log.call_args[0][0] == logging.WARNING
        assert (
            "insufficient memory"
            in mock_fr_child.log.call_args[0][1] % (mock_fr_child.log.call_args[0][2:])
        )

        mock_propose.reset_mock()
        mock_fr_logger.reset_mock()
        mock_fr_child.reset_mock()
        mock_events_client.emit.reset_mock()

        # Step 2: Pod transitions to Running (problem resolved)
        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=pod_uid,
            name="test-pod",
            namespace="default",
            labels=base_labels,
            status={
                "phase": "Running",
                "containerStatuses": [
                    {
                        "name": "main",
                        "state": {"running": {"startedAt": "2024-01-01T00:00:00Z"}},
                    }
                ],
            },
            logger=MagicMock(),
        )

        # No InfrastructurePending for Running pods
        mock_propose.assert_not_called()
        # No diagnosis for healthy Running pod
        mock_fr_logger.assert_not_called()
        # Event should still be emitted
        assert mock_events_client.emit.call_count == 1
        assert (
            mock_events_client.emit.call_args[1]["event"].event
            == "prefect.kubernetes.pod.running"
        )

    async def test_crash_loop_then_oom_lifecycle(
        self,
        mock_events_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Simulate a pod that crash-loops then terminates with OOMKilled.

        Verifies that each phase produces the correct diagnosis and that
        the diagnosis content changes as the failure condition evolves.
        """
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        mock_fr_logger = MagicMock()
        mock_fr_child = MagicMock()
        mock_fr_logger.return_value = mock_fr_child
        mock_fr_child.getChild.return_value = mock_fr_child
        monkeypatch.setattr(
            "prefect_kubernetes.observer.flow_run_logger", mock_fr_logger
        )

        base_labels = {
            "prefect.io/flow-run-id": str(flow_run_id),
            "prefect.io/flow-run-name": "my-flow-run",
        }

        # Step 1: CrashLoopBackOff
        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=pod_uid,
            name="test-pod",
            namespace="default",
            labels=base_labels,
            status={
                "phase": "Running",
                "containerStatuses": [
                    {
                        "name": "worker",
                        "state": {
                            "waiting": {
                                "reason": "CrashLoopBackOff",
                                "message": "back-off 5m0s restarting failed container",
                            }
                        },
                        "restartCount": 5,
                    }
                ],
            },
            logger=MagicMock(),
        )

        assert mock_fr_child.log.call_count == 1
        first_log = mock_fr_child.log.call_args[0]
        assert first_log[0] == logging.ERROR
        assert "crash-looping" in first_log[1] % first_log[2:]

        mock_fr_logger.reset_mock()
        mock_fr_child.reset_mock()

        # Step 2: Pod terminates with OOMKilled
        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=pod_uid,
            name="test-pod",
            namespace="default",
            labels=base_labels,
            status={
                "phase": "Failed",
                "containerStatuses": [
                    {
                        "name": "worker",
                        "state": {
                            "terminated": {
                                "reason": "OOMKilled",
                                "exitCode": 137,
                            }
                        },
                    }
                ],
            },
            logger=MagicMock(),
        )

        assert mock_fr_child.log.call_count == 1
        second_log = mock_fr_child.log.call_args[0]
        assert second_log[0] == logging.ERROR
        assert "OOMKilled" in second_log[1] % second_log[2:]

    async def test_evicted_pod_lifecycle(
        self,
        mock_events_client: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Simulate a pod-level eviction (status.reason = Evicted).

        Verifies the diagnosis log is WARNING-level and the event is
        rewritten to 'evicted' with the eviction reason in the resource.
        """
        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        mock_fr_logger = MagicMock()
        mock_fr_child = MagicMock()
        mock_fr_logger.return_value = mock_fr_child
        mock_fr_child.getChild.return_value = mock_fr_child
        monkeypatch.setattr(
            "prefect_kubernetes.observer.flow_run_logger", mock_fr_logger
        )

        await _replicate_pod_event(
            event={"type": "MODIFIED"},
            uid=pod_uid,
            name="test-pod",
            namespace="default",
            labels={
                "prefect.io/flow-run-id": str(flow_run_id),
                "prefect.io/flow-run-name": "my-flow-run",
            },
            status={
                "phase": "Failed",
                "reason": "Evicted",
                "message": "The node was low on resource: memory.",
            },
            logger=MagicMock(),
        )

        # Diagnosis log at WARNING level
        mock_fr_child.log.assert_called_once()
        assert mock_fr_child.log.call_args[0][0] == logging.WARNING
        assert (
            "evicted"
            in (
                mock_fr_child.log.call_args[0][1] % mock_fr_child.log.call_args[0][2:]
            ).lower()
        )

        # Event should still be emitted (phase rewritten won't apply here
        # since there are no containerStatuses with terminated reason)
        assert mock_events_client.emit.call_count == 1


class TestMarkFlowRunAsCrashed:
    @pytest.fixture
    def flow_run_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def base_kwargs(self, flow_run_id):
        return {
            "event": {"type": "MODIFIED"},
            "name": "test-job",
            "labels": {"prefect.io/flow-run-id": str(flow_run_id)},
            "status": {"failed": 7},
            "logger": MagicMock(),
            "spec": {"backoffLimit": 6},
            "namespace": "default",
        }

    async def test_skips_paused_states(
        self, mock_orchestration_client: AsyncMock, flow_run_id, base_kwargs
    ):
        flow_run = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="PAUSED", name="Suspended"),
        )
        mock_orchestration_client.read_flow_run.return_value = flow_run

        with pytest.MonkeyPatch.context() as m:
            mock_propose = AsyncMock()
            m.setattr("prefect_kubernetes.observer.propose_state", mock_propose)
            await _mark_flow_run_as_crashed(**base_kwargs)
            mock_propose.assert_not_called()

    async def test_skips_final_states(
        self, mock_orchestration_client: AsyncMock, flow_run_id, base_kwargs
    ):
        flow_run = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="COMPLETED", name="Completed"),
        )
        mock_orchestration_client.read_flow_run.return_value = flow_run

        with pytest.MonkeyPatch.context() as m:
            mock_propose = AsyncMock()
            m.setattr("prefect_kubernetes.observer.propose_state", mock_propose)
            await _mark_flow_run_as_crashed(**base_kwargs)
            mock_propose.assert_not_called()

    async def test_skips_scheduled_states(
        self, mock_orchestration_client: AsyncMock, flow_run_id, base_kwargs
    ):
        flow_run = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="SCHEDULED", name="Scheduled"),
        )
        mock_orchestration_client.read_flow_run.return_value = flow_run

        with pytest.MonkeyPatch.context() as m:
            mock_propose = AsyncMock()
            m.setattr("prefect_kubernetes.observer.propose_state", mock_propose)
            await _mark_flow_run_as_crashed(**base_kwargs)
            mock_propose.assert_not_called()

    async def test_marks_run_crashed_when_job_deleted(
        self,
        mock_orchestration_client: AsyncMock,
        flow_run_id,
        base_kwargs,
        monkeypatch,
    ):
        """A deleted job never retries, so nothing else would finalize the run."""
        mock_orchestration_client.read_flow_run.return_value = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="RUNNING", name="Running"),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_k8s_jobs", AsyncMock(return_value=[])
        )
        mock_propose = AsyncMock()
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        await _mark_flow_run_as_crashed(
            **{**base_kwargs, "event": {"type": "DELETED"}, "status": {}}
        )

        mock_propose.assert_called_once()
        assert (
            mock_propose.call_args.kwargs["state"].message
            == "Kubernetes job was deleted"
        )

    async def test_skips_cancelling_run_when_job_deleted(
        self,
        mock_orchestration_client: AsyncMock,
        flow_run_id,
        base_kwargs,
        monkeypatch,
    ):
        """Cancellation deletes the job itself and finalizes the run as Cancelled."""
        mock_orchestration_client.read_flow_run.return_value = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="CANCELLING", name="Cancelling"),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_k8s_jobs", AsyncMock(return_value=[])
        )
        mock_propose = AsyncMock()
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        await _mark_flow_run_as_crashed(
            **{**base_kwargs, "event": {"type": "DELETED"}, "status": {}}
        )

        mock_propose.assert_not_called()

    async def test_abort_on_crash_proposal_is_noop(
        self,
        mock_orchestration_client: AsyncMock,
        flow_run_id,
        base_kwargs,
        monkeypatch,
    ):
        """A concurrent transition to a terminal state makes propose_state raise
        Abort. It must be swallowed so it does not escape the handler and stop
        the kopf Jobs watcher for the worker process."""
        running_run = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="RUNNING", name="Running"),
        )
        mock_orchestration_client.read_flow_run.return_value = running_run

        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_k8s_jobs",
            AsyncMock(return_value=[]),
        )
        mock_send = MagicMock()
        monkeypatch.setattr(
            "prefect_kubernetes.observer._send_crashed_pod_logs", mock_send
        )
        mock_propose = AsyncMock(
            side_effect=Abort("Run is already in terminal state COMPLETED.")
        )
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        # Must not raise, otherwise kopf stops the Jobs watcher.
        await _mark_flow_run_as_crashed(**base_kwargs)

        mock_propose.assert_called_once()
        mock_send.assert_not_called()


class TestFetchCrashedPodLogs:
    @pytest.fixture
    def flow_run_id(self):
        return str(uuid.uuid4())

    @pytest.fixture
    def mock_k8s_client(self):
        """Creates a mock Kubernetes client with CoreV1Api.

        The primary container is named `prefect-job`, matching the default
        used by the Prefect Kubernetes worker.
        """
        client = AsyncMock()
        core_client = AsyncMock()

        container = MagicMock()
        container.name = "prefect-job"
        pod = MagicMock()
        pod.metadata.name = "test-pod-abc123"
        pod.metadata.creation_timestamp = "2026-01-01T00:00:00Z"
        pod.status.phase = "Failed"
        pod.spec.init_containers = None
        pod.spec.containers = [container]

        pods_response = MagicMock()
        pods_response.items = [pod]

        core_client.list_namespaced_pod.return_value = pods_response
        core_client.read_namespaced_pod_log.return_value = (
            "Traceback (most recent call last):\n"
            '  File "flow.py", line 1, in <module>\n'
            "    import nonexistent_package\n"
            "ModuleNotFoundError: No module named 'nonexistent_package'\n"
        )

        return client, core_client

    async def test_fetches_logs_for_crashed_pod(
        self, flow_run_id, mock_k8s_client, monkeypatch
    ):
        client, core_client = mock_k8s_client
        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_kubernetes_client",
            AsyncMock(return_value=client),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer.CoreV1Api", lambda c: core_client
        )

        result = await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name="test-job",
            namespace="default",
            logger=MagicMock(),
        )

        assert result is not None
        assert len(result) == 1
        assert result[0].container_name == "prefect-job"
        assert any("ModuleNotFoundError" in line for line in result[0].lines)

    async def test_filters_pods_by_job_name(
        self, flow_run_id, mock_k8s_client, monkeypatch
    ):
        """Verify list_namespaced_pod uses job-name label, not flow-run-id."""
        client, core_client = mock_k8s_client
        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_kubernetes_client",
            AsyncMock(return_value=client),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer.CoreV1Api", lambda c: core_client
        )

        await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name="my-specific-job",
            namespace="test-ns",
            logger=MagicMock(),
        )

        core_client.list_namespaced_pod.assert_called_once_with(
            namespace="test-ns",
            label_selector="job-name=my-specific-job",
        )

    async def test_returns_none_when_disabled(self, flow_run_id, monkeypatch):
        monkeypatch.setattr(
            "prefect_kubernetes.observer.settings.observer.forward_crashed_run_logs",
            False,
        )

        result = await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name="test-job",
            namespace="default",
            logger=MagicMock(),
        )
        assert result is None

    async def test_returns_none_when_no_pods(self, flow_run_id, monkeypatch):
        client = AsyncMock()
        core_client = AsyncMock()
        core_client.list_namespaced_pod.return_value = MagicMock(items=[])

        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_kubernetes_client",
            AsyncMock(return_value=client),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer.CoreV1Api", lambda c: core_client
        )

        result = await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name="test-job",
            namespace="default",
            logger=MagicMock(),
        )
        assert result is None

    async def test_returns_none_on_log_fetch_failure(
        self, flow_run_id, mock_k8s_client, monkeypatch
    ):
        client, core_client = mock_k8s_client
        core_client.read_namespaced_pod_log.side_effect = Exception("404 Not Found")

        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_kubernetes_client",
            AsyncMock(return_value=client),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer.CoreV1Api", lambda c: core_client
        )

        result = await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name="test-job",
            namespace="default",
            logger=MagicMock(),
        )
        assert result is None

    async def test_returns_none_on_empty_logs(
        self, flow_run_id, mock_k8s_client, monkeypatch
    ):
        client, core_client = mock_k8s_client
        core_client.read_namespaced_pod_log.return_value = ""

        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_kubernetes_client",
            AsyncMock(return_value=client),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer.CoreV1Api", lambda c: core_client
        )

        result = await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name="test-job",
            namespace="default",
            logger=MagicMock(),
        )
        assert result is None

    async def test_prioritizes_primary_container_over_sidecar(
        self, flow_run_id, monkeypatch
    ):
        """When the prefect-job container has logs, sidecar logs are excluded."""
        client = AsyncMock()
        core_client = AsyncMock()

        primary = MagicMock()
        primary.name = "prefect-job"
        sidecar = MagicMock()
        sidecar.name = "istio-proxy"

        pod = MagicMock()
        pod.metadata.name = "test-pod"
        pod.metadata.creation_timestamp = "2026-01-01T00:00:00Z"
        pod.status.phase = "Failed"
        pod.spec.init_containers = None
        pod.spec.containers = [sidecar, primary]

        core_client.list_namespaced_pod.return_value = MagicMock(items=[pod])

        async def _read_log(name, namespace, container, tail_lines, **kwargs):
            if container == "prefect-job":
                return "ImportError: cannot import name 'foo'\n"
            return "sidecar noise line 1\nsidecar noise line 2\n"

        core_client.read_namespaced_pod_log.side_effect = _read_log

        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_kubernetes_client",
            AsyncMock(return_value=client),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer.CoreV1Api", lambda c: core_client
        )

        result = await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name="test-job",
            namespace="default",
            logger=MagicMock(),
        )

        assert result is not None
        all_lines = [line for entry in result for line in entry.lines]
        assert any("ImportError" in line for line in all_lines)
        assert not any("sidecar noise" in line for line in all_lines)

    async def test_falls_back_to_sidecar_when_primary_empty(
        self, flow_run_id, monkeypatch
    ):
        """When the prefect-job container has no logs, other containers are included."""
        client = AsyncMock()
        core_client = AsyncMock()

        primary = MagicMock()
        primary.name = "prefect-job"
        sidecar = MagicMock()
        sidecar.name = "log-shipper"

        pod = MagicMock()
        pod.metadata.name = "test-pod"
        pod.metadata.creation_timestamp = "2026-01-01T00:00:00Z"
        pod.status.phase = "Failed"
        pod.spec.init_containers = None
        pod.spec.containers = [primary, sidecar]

        core_client.list_namespaced_pod.return_value = MagicMock(items=[pod])

        async def _read_log(name, namespace, container, tail_lines, **kwargs):
            if container == "prefect-job":
                return ""
            return "sidecar saw: OOMKilled\n"

        core_client.read_namespaced_pod_log.side_effect = _read_log

        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_kubernetes_client",
            AsyncMock(return_value=client),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer.CoreV1Api", lambda c: core_client
        )

        result = await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name="test-job",
            namespace="default",
            logger=MagicMock(),
        )

        assert result is not None
        all_lines = [line for entry in result for line in entry.lines]
        assert any("sidecar saw: OOMKilled" in line for line in all_lines)

    async def test_falls_back_to_init_container_when_primary_empty(
        self, flow_run_id, monkeypatch
    ):
        """When the prefect-job container has no logs, init containers are included."""
        client = AsyncMock()
        core_client = AsyncMock()

        init_container = MagicMock()
        init_container.name = "init-setup"
        primary = MagicMock()
        primary.name = "prefect-job"

        pod = MagicMock()
        pod.metadata.name = "test-pod"
        pod.metadata.creation_timestamp = "2026-01-01T00:00:00Z"
        pod.status.phase = "Failed"
        pod.spec.init_containers = [init_container]
        pod.spec.containers = [primary]

        core_client.list_namespaced_pod.return_value = MagicMock(items=[pod])

        async def _read_log(name, namespace, container, tail_lines, **kwargs):
            if container == "prefect-job":
                return ""
            return "init failed: permission denied\n"

        core_client.read_namespaced_pod_log.side_effect = _read_log

        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_kubernetes_client",
            AsyncMock(return_value=client),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer.CoreV1Api", lambda c: core_client
        )

        result = await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name="test-job",
            namespace="default",
            logger=MagicMock(),
        )

        assert result is not None
        assert result[0].container_type == "init container"
        assert result[0].container_name == "init-setup"

    async def test_custom_container_name_includes_all_containers(
        self, flow_run_id, monkeypatch
    ):
        """When no prefect-job container exists, all containers are included
        since we can't reliably identify the flow container."""
        client = AsyncMock()
        core_client = AsyncMock()

        custom = MagicMock()
        custom.name = "my-custom-flow-container"
        sidecar = MagicMock()
        sidecar.name = "istio-proxy"

        pod = MagicMock()
        pod.metadata.name = "test-pod"
        pod.metadata.creation_timestamp = "2026-01-01T00:00:00Z"
        pod.status.phase = "Failed"
        pod.spec.init_containers = None
        pod.spec.containers = [sidecar, custom]

        core_client.list_namespaced_pod.return_value = MagicMock(items=[pod])

        async def _read_log(name, namespace, container, tail_lines, **kwargs):
            if container == "my-custom-flow-container":
                return "KeyError: 'missing_config'\n"
            return "envoy proxy ready\n"

        core_client.read_namespaced_pod_log.side_effect = _read_log

        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_kubernetes_client",
            AsyncMock(return_value=client),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer.CoreV1Api", lambda c: core_client
        )

        result = await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name="test-job",
            namespace="default",
            logger=MagicMock(),
        )

        assert result is not None
        # Both containers should be included
        container_names = {entry.container_name for entry in result}
        assert "my-custom-flow-container" in container_names
        assert "istio-proxy" in container_names

    async def test_single_container_always_primary(self, flow_run_id, monkeypatch):
        """A pod with a single container uses it as primary regardless of name."""
        client = AsyncMock()
        core_client = AsyncMock()

        container = MagicMock()
        container.name = "weird-name"

        pod = MagicMock()
        pod.metadata.name = "test-pod"
        pod.metadata.creation_timestamp = "2026-01-01T00:00:00Z"
        pod.status.phase = "Failed"
        pod.spec.init_containers = None
        pod.spec.containers = [container]

        core_client.list_namespaced_pod.return_value = MagicMock(items=[pod])
        core_client.read_namespaced_pod_log.return_value = "crash output\n"

        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_kubernetes_client",
            AsyncMock(return_value=client),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer.CoreV1Api", lambda c: core_client
        )

        result = await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name="test-job",
            namespace="default",
            logger=MagicMock(),
        )

        assert result is not None
        assert any("crash output" in line for line in result[0].lines)

    async def test_newest_retry_pod_logs_appear_first(self, flow_run_id, monkeypatch):
        """Pods are sorted newest-first so the final retry's logs survive truncation."""
        client = AsyncMock()
        core_client = AsyncMock()

        old_pod = MagicMock()
        old_pod.metadata.name = "pod-attempt-1"
        old_pod.metadata.creation_timestamp = "2026-01-01T00:00:00Z"
        old_pod.status.phase = "Failed"
        old_pod.spec.init_containers = None
        old_container = MagicMock()
        old_container.name = "prefect-job"
        old_pod.spec.containers = [old_container]

        new_pod = MagicMock()
        new_pod.metadata.name = "pod-attempt-2"
        new_pod.metadata.creation_timestamp = "2026-01-01T00:01:00Z"
        new_pod.status.phase = "Failed"
        new_pod.spec.init_containers = None
        new_container = MagicMock()
        new_container.name = "prefect-job"
        new_pod.spec.containers = [new_container]

        # Return pods in oldest-first order (API default)
        core_client.list_namespaced_pod.return_value = MagicMock(
            items=[old_pod, new_pod]
        )

        async def _read_log(name, namespace, container, tail_lines, **kwargs):
            if name == "pod-attempt-2":
                return "FINAL ATTEMPT: ModuleNotFoundError\n"
            return "OLDER ATTEMPT: some earlier error\n"

        core_client.read_namespaced_pod_log.side_effect = _read_log

        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_kubernetes_client",
            AsyncMock(return_value=client),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer.CoreV1Api", lambda c: core_client
        )

        result = await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name="test-job",
            namespace="default",
            logger=MagicMock(),
        )

        assert result is not None
        assert len(result) == 2
        # The newest pod's entry should come first
        assert result[0].pod_name == "pod-attempt-2"
        assert result[1].pod_name == "pod-attempt-1"

    async def test_excludes_only_succeeded_pods(self, flow_run_id, monkeypatch):
        """Succeeded pods are excluded; Failed and Running pods are included.

        Running pods are included because with restartPolicy: OnFailure the
        pod stays Running while containers crash inside it.
        """
        client = AsyncMock()
        core_client = AsyncMock()

        def _make_pod(name, phase, timestamp):
            pod = MagicMock()
            pod.metadata.name = name
            pod.metadata.creation_timestamp = timestamp
            pod.status.phase = phase
            pod.spec.init_containers = None
            c = MagicMock()
            c.name = "prefect-job"
            pod.spec.containers = [c]
            return pod

        succeeded_pod = _make_pod("pod-ok", "Succeeded", "2026-01-01T00:00:00Z")
        running_pod = _make_pod("pod-crashing", "Running", "2026-01-01T00:00:30Z")
        failed_pod = _make_pod("pod-bad", "Failed", "2026-01-01T00:01:00Z")

        core_client.list_namespaced_pod.return_value = MagicMock(
            items=[succeeded_pod, running_pod, failed_pod]
        )

        async def _read_log(name, namespace, container, tail_lines, **kwargs):
            return f"logs from {name}\n"

        core_client.read_namespaced_pod_log.side_effect = _read_log

        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_kubernetes_client",
            AsyncMock(return_value=client),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer.CoreV1Api", lambda c: core_client
        )

        result = await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name="test-job",
            namespace="default",
            logger=MagicMock(),
        )

        assert result is not None
        pod_names = {entry.pod_name for entry in result}
        assert "pod-bad" in pod_names
        assert "pod-crashing" in pod_names
        assert "pod-ok" not in pod_names

    async def test_prefers_previous_container_logs(
        self, flow_run_id, mock_k8s_client, monkeypatch
    ):
        """With restartPolicy: OnFailure, the previous container instance
        holds the crash traceback. Verify it is preferred over current logs."""
        client, core_client = mock_k8s_client

        async def _read_log(name, namespace, container, tail_lines, **kwargs):
            if kwargs.get("previous"):
                return "PREVIOUS: ImportError: no module named 'foo'\n"
            return "CURRENT: container starting up...\n"

        core_client.read_namespaced_pod_log.side_effect = _read_log

        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_kubernetes_client",
            AsyncMock(return_value=client),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer.CoreV1Api", lambda c: core_client
        )

        result = await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name="test-job",
            namespace="default",
            logger=MagicMock(),
        )

        assert result is not None
        all_lines = [line for entry in result for line in entry.lines]
        assert any("PREVIOUS: ImportError" in line for line in all_lines)
        assert not any("CURRENT:" in line for line in all_lines)

    async def test_falls_back_to_current_when_no_previous(
        self, flow_run_id, mock_k8s_client, monkeypatch
    ):
        """When there is no previous container instance, current logs are used."""
        client, core_client = mock_k8s_client

        async def _read_log(name, namespace, container, tail_lines, **kwargs):
            if kwargs.get("previous"):
                raise Exception("previous terminated container not found")
            return "ModuleNotFoundError: no module named 'bar'\n"

        core_client.read_namespaced_pod_log.side_effect = _read_log

        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_kubernetes_client",
            AsyncMock(return_value=client),
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer.CoreV1Api", lambda c: core_client
        )

        result = await _fetch_crashed_pod_logs(
            flow_run_id=flow_run_id,
            job_name="test-job",
            namespace="default",
            logger=MagicMock(),
        )

        assert result is not None
        all_lines = [line for entry in result for line in entry.lines]
        assert any("ModuleNotFoundError" in line for line in all_lines)

    def test_send_emits_individual_lines(self):
        """Each log line should be emitted as a separate log entry."""
        flow_run_id = str(uuid.uuid4())
        entries = [
            _ContainerLogEntry(
                pod_name="test-pod",
                container_name="prefect-job",
                container_type="container",
                lines=["line 1", "line 2", "line 3"],
            )
        ]

        with patch("prefect_kubernetes.observer.flow_run_logger") as mock_fr_logger:
            mock_child = MagicMock()
            mock_fr_logger.return_value.getChild.return_value = mock_child

            _send_crashed_pod_logs(flow_run_id=flow_run_id, entries=entries)

            # 1 header + 3 lines, all at error level
            assert mock_child.error.call_count == 4
            assert "Container logs from" in mock_child.error.call_args_list[0][0][0]
            assert mock_child.error.call_args_list[1][0][0] == "line 1"
            assert mock_child.error.call_args_list[2][0][0] == "line 2"
            assert mock_child.error.call_args_list[3][0][0] == "line 3"

    def test_send_truncates_oversized_lines(self):
        """Individual lines exceeding max log size should be truncated."""
        flow_run_id = str(uuid.uuid4())
        large_line = "x" * 2_000_000
        entries = [
            _ContainerLogEntry(
                pod_name="test-pod",
                container_name="prefect-job",
                container_type="container",
                lines=[large_line],
            )
        ]

        with patch("prefect_kubernetes.observer.flow_run_logger") as mock_fr_logger:
            mock_child = MagicMock()
            mock_fr_logger.return_value.getChild.return_value = mock_child

            _send_crashed_pod_logs(flow_run_id=flow_run_id, entries=entries)

            # 1 header + 1 truncated line
            assert mock_child.error.call_count == 2
            logged_text = mock_child.error.call_args_list[1][0][0]
            assert "[truncated]" in logged_text
            assert len(logged_text) <= 1_000_000

    async def test_mark_crashed_fetches_logs_before_wait_loop(
        self, mock_orchestration_client, monkeypatch
    ):
        """_mark_flow_run_as_crashed fetches logs eagerly before the 30s wait loop."""
        from contextlib import contextmanager

        import anyio as _anyio

        flow_run_id = uuid.uuid4()

        pending_run = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="PENDING", name="Pending"),
        )
        mock_orchestration_client.read_flow_run.return_value = pending_run

        _real_move_on_after = _anyio.move_on_after

        @contextmanager
        def _fast_move_on_after(_timeout):
            with _real_move_on_after(0.01) as scope:
                yield scope

        monkeypatch.setattr(
            "prefect_kubernetes.observer.anyio.move_on_after",
            _fast_move_on_after,
        )
        _real_sleep = _anyio.sleep

        async def _fast_sleep(_seconds):
            await _real_sleep(0)

        monkeypatch.setattr(
            "prefect_kubernetes.observer.anyio.sleep",
            _fast_sleep,
        )

        # Track call order to verify fetch happens before the wait loop
        call_order: list[str] = []

        mock_entries = [
            _ContainerLogEntry(
                pod_name="test-pod",
                container_name="prefect-job",
                container_type="container",
                lines=["some logs"],
            )
        ]

        async def mock_fetch(**kwargs):
            call_order.append("fetch")
            return mock_entries

        async def mock_get_jobs(flow_run_id, namespace, logger):
            call_order.append("get_jobs")
            return []

        monkeypatch.setattr(
            "prefect_kubernetes.observer._fetch_crashed_pod_logs", mock_fetch
        )
        monkeypatch.setattr("prefect_kubernetes.observer._get_k8s_jobs", mock_get_jobs)

        mock_send = MagicMock()
        monkeypatch.setattr(
            "prefect_kubernetes.observer._send_crashed_pod_logs", mock_send
        )
        # propose_state returns an accepted Crashed state
        mock_propose = AsyncMock(return_value=State(type="CRASHED", name="Crashed"))
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        await _mark_flow_run_as_crashed(
            event={"type": "MODIFIED"},
            name="test-job",
            labels={"prefect.io/flow-run-id": str(flow_run_id)},
            status={"failed": 7},
            logger=MagicMock(),
            spec={"backoffLimit": 6},
            namespace="default",
        )

        # fetch must happen before get_jobs (which is in the wait loop)
        assert call_order[0] == "fetch"
        assert "get_jobs" in call_order

        # send should be called with the fetched entries
        mock_send.assert_called_once_with(
            flow_run_id=str(flow_run_id),
            entries=mock_entries,
        )
        mock_propose.assert_called_once()

    async def test_mark_crashed_skips_fetch_for_running_run(
        self, mock_orchestration_client, monkeypatch
    ):
        """_mark_flow_run_as_crashed should NOT fetch logs when flow run reached Running."""
        flow_run_id = uuid.uuid4()

        running_run = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="RUNNING", name="Running"),
        )
        mock_orchestration_client.read_flow_run.return_value = running_run

        mock_fetch = AsyncMock(return_value=None)
        monkeypatch.setattr(
            "prefect_kubernetes.observer._fetch_crashed_pod_logs", mock_fetch
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_k8s_jobs", AsyncMock(return_value=[])
        )
        mock_send = MagicMock()
        monkeypatch.setattr(
            "prefect_kubernetes.observer._send_crashed_pod_logs", mock_send
        )
        mock_propose = AsyncMock()
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        await _mark_flow_run_as_crashed(
            event={"type": "MODIFIED"},
            name="test-job",
            labels={"prefect.io/flow-run-id": str(flow_run_id)},
            status={"failed": 7},
            logger=MagicMock(),
            spec={"backoffLimit": 6},
            namespace="default",
        )

        mock_fetch.assert_not_called()
        mock_send.assert_not_called()
        mock_propose.assert_called_once()

    async def test_mark_crashed_skips_logs_when_crash_proposal_rejected(
        self, mock_orchestration_client, monkeypatch
    ):
        """Logs must not be forwarded if propose_state rejects the Crashed transition."""
        from contextlib import contextmanager

        import anyio as _anyio

        flow_run_id = uuid.uuid4()

        pending_run = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="PENDING", name="Pending"),
        )
        mock_orchestration_client.read_flow_run.return_value = pending_run

        _real_move_on_after = _anyio.move_on_after

        @contextmanager
        def _fast_move_on_after(_timeout):
            with _real_move_on_after(0.01) as scope:
                yield scope

        monkeypatch.setattr(
            "prefect_kubernetes.observer.anyio.move_on_after",
            _fast_move_on_after,
        )
        _real_sleep = _anyio.sleep

        async def _fast_sleep(_seconds):
            await _real_sleep(0)

        monkeypatch.setattr(
            "prefect_kubernetes.observer.anyio.sleep",
            _fast_sleep,
        )

        mock_fetch = AsyncMock(
            return_value=[
                _ContainerLogEntry(
                    pod_name="test-pod",
                    container_name="prefect-job",
                    container_type="container",
                    lines=["captured crash logs"],
                )
            ]
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer._fetch_crashed_pod_logs", mock_fetch
        )
        monkeypatch.setattr(
            "prefect_kubernetes.observer._get_k8s_jobs",
            AsyncMock(return_value=[]),
        )

        mock_send = MagicMock()
        monkeypatch.setattr(
            "prefect_kubernetes.observer._send_crashed_pod_logs", mock_send
        )
        # propose_state rejects the crash — returns Running instead
        mock_propose = AsyncMock(return_value=State(type="RUNNING", name="Running"))
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        await _mark_flow_run_as_crashed(
            event={"type": "MODIFIED"},
            name="test-job",
            labels={"prefect.io/flow-run-id": str(flow_run_id)},
            status={"failed": 7},
            logger=MagicMock(),
            spec={"backoffLimit": 6},
            namespace="default",
        )

        mock_fetch.assert_called_once()
        mock_propose.assert_called_once()
        # Logs must NOT be sent because the crash was rejected
        mock_send.assert_not_called()


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


class TestLoggingConfiguration:
    """Tests for the logging configuration logic in start_observer()"""

    @pytest.mark.usefixtures("mock_events_client", "mock_orchestration_client")
    def test_json_formatter_configures_kopf_logger(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Test that when Prefect uses JSON formatting, kopf logger gets its own
        handler with KopfObjectJsonFormatter and propagation is disabled.
        """
        # Stop any existing observer first
        stop_observer()

        # Set up Prefect to use JSON formatting
        monkeypatch.setenv("PREFECT_LOGGING_HANDLERS_CONSOLE_FORMATTER", "json")

        # Import and setup logging fresh to pick up env var
        from prefect.logging.configuration import PROCESS_LOGGING_CONFIG, setup_logging

        PROCESS_LOGGING_CONFIG.clear()
        setup_logging(incremental=False)

        # Clear any existing kopf logger configuration
        kopf_logger = logging.getLogger("kopf")
        kopf_logger.handlers.clear()
        kopf_logger.propagate = True

        # Start the observer which should configure kopf logging
        try:
            start_observer()
            sleep(0.5)  # Give it time to configure

            # Verify kopf logger has its own handler
            assert len(kopf_logger.handlers) > 0, "kopf logger should have a handler"

            # Verify the handler has the correct formatter
            handler = kopf_logger.handlers[0]
            assert isinstance(handler.formatter, KopfObjectJsonFormatter), (
                f"Expected KopfObjectJsonFormatter, got {type(handler.formatter)}"
            )

            # Verify propagation is disabled
            assert kopf_logger.propagate is False, (
                "kopf logger propagation should be disabled"
            )
        finally:
            stop_observer()
            monkeypatch.delenv("PREFECT_LOGGING_HANDLERS_CONSOLE_FORMATTER")

    @pytest.mark.usefixtures("mock_events_client", "mock_orchestration_client")
    def test_standard_formatter_uses_default_behavior(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Test that when Prefect uses standard formatting (default),
        kopf logger uses default propagation behavior.
        """
        # Stop any existing observer first
        stop_observer()

        # Use default logging configuration (standard formatter)
        from prefect.logging.configuration import PROCESS_LOGGING_CONFIG, setup_logging

        PROCESS_LOGGING_CONFIG.clear()
        setup_logging(incremental=False)

        # Clear any existing kopf logger configuration
        kopf_logger = logging.getLogger("kopf")
        kopf_logger.handlers.clear()
        kopf_logger.propagate = True

        # Start the observer
        try:
            start_observer()
            sleep(0.5)

            # Verify kopf logger doesn't have a dedicated handler added by start_observer
            # (it should propagate to root logger since we're using standard formatting)
            assert len(kopf_logger.handlers) == 0, (
                "kopf logger should not have handlers with standard formatting"
            )

            # Verify propagation is still enabled (default behavior)
            assert kopf_logger.propagate is True, (
                "kopf logger propagation should remain enabled with standard formatting"
            )
        finally:
            stop_observer()

    @pytest.mark.usefixtures("mock_events_client", "mock_orchestration_client")
    def test_no_duplicate_logs_with_json_formatting(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Test that kopf logs don't appear duplicated when JSON formatting is enabled.
        """
        # Stop any existing observer first
        stop_observer()

        # Set up JSON formatting
        monkeypatch.setenv("PREFECT_LOGGING_HANDLERS_CONSOLE_FORMATTER", "json")

        from prefect.logging.configuration import PROCESS_LOGGING_CONFIG, setup_logging

        PROCESS_LOGGING_CONFIG.clear()
        setup_logging(incremental=False)

        # Clear kopf logger
        kopf_logger = logging.getLogger("kopf.test")
        kopf_logger.handlers.clear()
        kopf_logger.propagate = True

        try:
            start_observer()
            sleep(0.5)

            # Create a custom handler to capture logs
            # (caplog won't work since propagation is disabled)
            captured_logs: list[logging.LogRecord] = []

            class CaptureHandler(logging.Handler):
                def emit(self, record: logging.LogRecord):
                    captured_logs.append(record)

            capture_handler = CaptureHandler()
            kopf_logger.addHandler(capture_handler)

            # Emit a test message
            kopf_logger.warning("Test message for duplicate check")

            # Count how many times the message appears
            matching_records = [
                r
                for r in captured_logs
                if "Test message for duplicate check" in r.message
            ]

            assert len(matching_records) == 1, (
                f"Expected 1 log message, got {len(matching_records)}"
            )
        finally:
            stop_observer()
            monkeypatch.delenv("PREFECT_LOGGING_HANDLERS_CONSOLE_FORMATTER")

    @pytest.mark.usefixtures("mock_events_client", "mock_orchestration_client")
    def test_kopf_logs_visible_with_json_formatting(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """
        Test that kopf logs are actually emitted and visible when JSON formatting is enabled.
        """
        # Stop any existing observer first
        stop_observer()

        # Set up JSON formatting
        monkeypatch.setenv("PREFECT_LOGGING_HANDLERS_CONSOLE_FORMATTER", "json")

        from prefect.logging.configuration import PROCESS_LOGGING_CONFIG, setup_logging

        PROCESS_LOGGING_CONFIG.clear()
        setup_logging(incremental=False)

        # Clear kopf logger
        kopf_logger = logging.getLogger("kopf.test")
        kopf_logger.handlers.clear()
        kopf_logger.propagate = True

        try:
            start_observer()
            sleep(0.5)

            # Create a string buffer to capture output
            log_capture = StringIO()
            test_handler = logging.StreamHandler(log_capture)
            test_handler.setFormatter(KopfObjectJsonFormatter())
            kopf_logger.addHandler(test_handler)

            # Emit a test log message
            kopf_logger.warning("Test message for visibility check")

            # Get the captured output
            log_output = log_capture.getvalue()

            # Verify the message was emitted
            assert "Test message for visibility check" in log_output, (
                "kopf log message should be visible in output"
            )

            # Verify it's JSON formatted
            assert '"message"' in log_output or '"msg"' in log_output, (
                "Log output should be JSON formatted"
            )
        finally:
            stop_observer()
            monkeypatch.delenv("PREFECT_LOGGING_HANDLERS_CONSOLE_FORMATTER")
