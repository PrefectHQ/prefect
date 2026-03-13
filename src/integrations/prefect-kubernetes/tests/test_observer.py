import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from io import StringIO
from time import sleep
from unittest.mock import AsyncMock, MagicMock

import pytest
from prefect_kubernetes._logging import KopfObjectJsonFormatter
from prefect_kubernetes.diagnostics import DiagnosisCode
from prefect_kubernetes.observer import (
    _mark_flow_run_as_crashed,
    _replicate_pod_event,
    start_observer,
    stop_observer,
)

from prefect.client.schemas.objects import FlowRun, State
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
        mock_propose = AsyncMock()
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
        from prefect.exceptions import ObjectNotFound

        flow_run_id = uuid.uuid4()
        mock_propose = AsyncMock()
        monkeypatch.setattr("prefect_kubernetes.observer.propose_state", mock_propose)

        mock_orchestration_client.read_flow_run.side_effect = ObjectNotFound(
            "Flow run not found"
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
        from prefect_kubernetes.observer import _last_diagnosis_cache

        flow_run_id = uuid.uuid4()
        pod_uid = str(uuid.uuid4())
        mock_logger = MagicMock()
        mock_child = MagicMock()
        mock_logger.return_value = mock_child
        mock_child.getChild.return_value = mock_child
        monkeypatch.setattr("prefect_kubernetes.observer.flow_run_logger", mock_logger)

        # Clear the cache to avoid interference from other tests
        _last_diagnosis_cache.clear()

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

        # Pod recovers (healthy status clears cache)
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
        mock_propose = AsyncMock()
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
        mock_propose = AsyncMock()
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


class TestSubflowFailureStateHandling:
    """Tests for subflow pod failure state forcing via handle_subflow_failure_state."""

    @pytest.fixture
    def mock_settings(self, monkeypatch: pytest.MonkeyPatch):
        """Return a helper that patches observer settings with the given state value."""

        def _patch(state: str | None):
            mock = MagicMock()
            mock.observer.handle_subflow_failure_state = state
            mock.observer.replicate_pod_events = False
            mock.observer.startup_event_concurrency = 5
            monkeypatch.setattr("prefect_kubernetes.observer.settings", mock)

        return _patch

    @pytest.mark.parametrize("target_state", ["failed", "crashed"])
    async def test_subflow_oom_killed_forces_state(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_settings,
        target_state: str,
    ):
        """Subflow pod OOMKilled should force flow run to failed or crashed."""
        mock_settings(target_state)
        flow_run_id = uuid.uuid4()

        await _replicate_pod_event(
            event={"type": "MODIFIED", "object": {"metadata": {}}},
            uid=str(uuid.uuid4()),
            name="test-pod",
            namespace="default",
            labels={
                "prefect.io/flow-run-id": str(flow_run_id),
                "prefect.io/flow-run-name": "test-subflow",
                "prefect.io/parent-task-run-id": str(uuid.uuid4()),
            },
            status={
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
            logger=MagicMock(),
        )

        mock_orchestration_client.set_flow_run_state.assert_called_once()
        call_kwargs = mock_orchestration_client.set_flow_run_state.call_args.kwargs
        assert call_kwargs["flow_run_id"] == flow_run_id
        assert call_kwargs["force"] is True
        assert call_kwargs["state"].name.lower() == target_state

    async def test_top_level_flow_oom_killed_does_not_force_state(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_settings,
    ):
        """Top-level flow run pods (no parent-task-run-id) must not be affected."""
        mock_settings("crashed")

        await _replicate_pod_event(
            event={"type": "MODIFIED", "object": {"metadata": {}}},
            uid=str(uuid.uuid4()),
            name="test-pod",
            namespace="default",
            labels={
                "prefect.io/flow-run-id": str(uuid.uuid4()),
                "prefect.io/flow-run-name": "test-flow",
                # no parent-task-run-id — top-level flow run
            },
            status={
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
            logger=MagicMock(),
        )

        mock_orchestration_client.set_flow_run_state.assert_not_called()

    async def test_setting_disabled_does_not_force_state(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_settings,
    ):
        """When handle_subflow_failure_state is None, no state should be forced."""
        mock_settings(None)

        await _replicate_pod_event(
            event={"type": "MODIFIED", "object": {"metadata": {}}},
            uid=str(uuid.uuid4()),
            name="test-pod",
            namespace="default",
            labels={
                "prefect.io/flow-run-id": str(uuid.uuid4()),
                "prefect.io/flow-run-name": "test-subflow",
                "prefect.io/parent-task-run-id": str(uuid.uuid4()),
            },
            status={
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
            logger=MagicMock(),
        )

        mock_orchestration_client.set_flow_run_state.assert_not_called()

    @pytest.mark.parametrize(
        "failure_status",
        [
            pytest.param(
                {
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
                id=DiagnosisCode.OOM_KILLED,
            ),
            pytest.param(
                {
                    "phase": "Pending",
                    "containerStatuses": [
                        {
                            "name": "main",
                            "state": {"waiting": {"reason": "ImagePullBackOff"}},
                        }
                    ],
                },
                id=DiagnosisCode.IMAGE_PULL_FAILED,
            ),
            pytest.param(
                {
                    "phase": "Running",
                    "containerStatuses": [
                        {
                            "name": "main",
                            "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                        }
                    ],
                },
                id=DiagnosisCode.CRASH_LOOP_BACK_OFF,
            ),
            pytest.param(
                {
                    "phase": "Failed",
                    "reason": "Evicted",
                    "message": "The node was low on resource: memory.",
                },
                id=DiagnosisCode.EVICTED_POD,
            ),
        ],
    )
    async def test_all_failure_conditions_force_state(
        self,
        mock_events_client: AsyncMock,
        mock_orchestration_client: AsyncMock,
        mock_settings,
        failure_status: dict,
    ):
        """All diagnosed failure conditions should force state for subflow pods."""
        mock_settings("crashed")

        await _replicate_pod_event(
            event={"type": "MODIFIED", "object": {"metadata": {}}},
            uid=str(uuid.uuid4()),
            name="test-pod",
            namespace="default",
            labels={
                "prefect.io/flow-run-id": str(uuid.uuid4()),
                "prefect.io/flow-run-name": "test-subflow",
                "prefect.io/parent-task-run-id": str(uuid.uuid4()),
            },
            status=failure_status,
            logger=MagicMock(),
        )

        mock_orchestration_client.set_flow_run_state.assert_called_once()
