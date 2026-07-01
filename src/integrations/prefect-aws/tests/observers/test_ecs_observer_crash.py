"""Tests for ECS observer mark_runs_as_crashed handler.

Covers the fix for #22410: ECS tasks that fail to start (stopCode
TaskFailedToStart with empty containers array) should be marked as
Crashed, not left in PENDING forever.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from prefect_aws.observers.ecs import mark_runs_as_crashed

from prefect.client.schemas import FlowRun, State
from prefect.client.schemas.objects import StateType


class TestMarkRunsAsCrashedTaskFailedToStart:
    """Tests verifying that TaskFailedToStart events produce a Crashed proposal."""

    @pytest.fixture
    def task_failed_to_start_event(self) -> dict:
        return {
            "detail": {
                "taskArn": "arn:aws:ecs:us-east-1:123456789:task/test-cluster/def456",
                "lastStatus": "STOPPED",
                "stopCode": "TaskFailedToStart",
                "stoppedReason": "TaskFailedToStart: RESOURCE:GPU",
                "containers": [],
            }
        }

    @pytest.fixture
    def sample_tags(self) -> dict:
        return {"prefect.io/flow-run-id": str(uuid.uuid4())}

    @pytest.fixture
    def running_flow_run(self, sample_tags) -> FlowRun:
        return FlowRun(
            id=uuid.UUID(sample_tags["prefect.io/flow-run-id"]),
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="RUNNING", name="Running"),
        )

    @patch("prefect_aws.observers.ecs.prefect.get_client")
    @patch("prefect_aws.observers.ecs.propose_state")
    async def test_task_failed_to_start_proposes_crashed(
        self,
        mock_propose_state,
        mock_get_client,
        task_failed_to_start_event,
        sample_tags,
        running_flow_run,
    ):
        """TaskFailedToStart with empty containers should propose a Crashed state."""
        flow_run_id = uuid.UUID(sample_tags["prefect.io/flow-run-id"])
        mock_client = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_get_client.return_value = mock_context
        mock_client.read_flow_run.return_value = running_flow_run

        await mark_runs_as_crashed(task_failed_to_start_event, sample_tags)

        mock_client.read_flow_run.assert_called_once_with(flow_run_id=flow_run_id)
        mock_propose_state.assert_called_once()

        call_args = mock_propose_state.call_args[1]
        proposed_state = call_args["state"]
        assert proposed_state.type == StateType.CRASHED
        assert proposed_state.name == "Crashed"
        assert call_args["flow_run_id"] == flow_run_id
        assert call_args["client"] == mock_client

    @patch("prefect_aws.observers.ecs.prefect.get_client")
    @patch("prefect_aws.observers.ecs.propose_state")
    async def test_normal_exit_with_containers_does_not_crash(
        self,
        mock_propose_state,
        mock_get_client,
        sample_tags,
        running_flow_run,
    ):
        """A normal STOPPED event with containers should NOT propose Crashed."""
        event = {
            "detail": {
                "taskArn": "arn:aws:ecs:us-east-1:123456789:task/cluster/abc123",
                "lastStatus": "STOPPED",
                "stopCode": "EssentialContainerExited",
                "stoppedReason": "Essential container in task exited",
                "containers": [
                    {"name": "prefect", "exitCode": 0},
                ],
            }
        }
        mock_client = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_get_client.return_value = mock_context
        mock_client.read_flow_run.return_value = running_flow_run

        await mark_runs_as_crashed(event, sample_tags)

        mock_propose_state.assert_not_called()

    @patch("prefect_aws.observers.ecs.prefect.get_client")
    @patch("prefect_aws.observers.ecs.propose_state")
    async def test_empty_containers_without_task_failed_does_not_crash(
        self,
        mock_propose_state,
        mock_get_client,
        sample_tags,
        running_flow_run,
    ):
        """Empty containers with a different stopCode should NOT propose Crashed."""
        event = {
            "detail": {
                "taskArn": "arn:aws:ecs:us-east-1:123456789:task/cluster/xyz789",
                "lastStatus": "STOPPED",
                "stopCode": "ServiceSchedulingStrategy",
                "containers": [],
            }
        }
        mock_client = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_get_client.return_value = mock_context
        mock_client.read_flow_run.return_value = running_flow_run

        await mark_runs_as_crashed(event, sample_tags)

        mock_propose_state.assert_not_called()

    @patch("prefect_aws.observers.ecs.prefect.get_client")
    @patch("prefect_aws.observers.ecs.propose_state")
    async def test_task_failed_to_start_crash_message_includes_reason(
        self,
        mock_propose_state,
        mock_get_client,
        task_failed_to_start_event,
        sample_tags,
        running_flow_run,
    ):
        """The Crashed message should include the stoppedReason from the event."""
        mock_client = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_get_client.return_value = mock_context
        mock_client.read_flow_run.return_value = running_flow_run

        await mark_runs_as_crashed(task_failed_to_start_event, sample_tags)

        call_args = mock_propose_state.call_args[1]
        crash_message = call_args.get("message", "")
        assert "TaskFailedToStart" in crash_message
        assert "RESOURCE:GPU" in crash_message
        assert "capacity provider" in crash_message

    @patch("prefect_aws.observers.ecs.prefect.get_client")
    @patch("prefect_aws.observers.ecs.propose_state")
    async def test_task_failed_to_start_skips_final_flow_run(
        self,
        mock_propose_state,
        mock_get_client,
        task_failed_to_start_event,
        sample_tags,
    ):
        """A TaskFailedToStart event should NOT crash a flow run in a final state."""
        flow_run_id = uuid.UUID(sample_tags["prefect.io/flow-run-id"])
        final_flow_run = FlowRun(
            id=flow_run_id,
            name="test-flow-run",
            flow_id=uuid.uuid4(),
            state=State(type="COMPLETED", name="Completed"),
        )
        mock_client = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_get_client.return_value = mock_context
        mock_client.read_flow_run.return_value = final_flow_run

        await mark_runs_as_crashed(task_failed_to_start_event, sample_tags)

        mock_propose_state.assert_not_called()

    @patch("prefect_aws.observers.ecs.prefect.get_client")
    @patch("prefect_aws.observers.ecs.propose_state")
    async def test_task_failed_to_start_missing_flow_run(
        self,
        mock_propose_state,
        mock_get_client,
        task_failed_to_start_event,
        sample_tags,
    ):
        """A TaskFailedToStart event should not crash when flow run is not found."""
        from prefect.exceptions import ObjectNotFound

        mock_client = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_get_client.return_value = mock_context
        mock_client.read_flow_run.side_effect = ObjectNotFound("Flow run not found")

        await mark_runs_as_crashed(task_failed_to_start_event, sample_tags)

        mock_propose_state.assert_not_called()
