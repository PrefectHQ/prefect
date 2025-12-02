"""
Test that child task runs are crashed when their parent flow run crashes.

This verifies the fix for https://github.com/PrefectHQ/prefect/issues/19594
where task runs would remain stuck in RUNNING state when their parent flow
run crashed (e.g., OOM killed in Kubernetes).
"""

from uuid import UUID

from prefect import get_client, task
from prefect.client.schemas import filters
from prefect.client.schemas.actions import FlowCreate, FlowRunCreate
from prefect.states import Crashed, Running, StateType


@task
def long_running_task(task_num: int):
    """A task that would run for a while."""
    return f"Task {task_num} completed"


async def test_child_task_runs_crash_when_flow_crashes():
    """
    When a flow run is marked as CRASHED, all non-terminal child task runs
    should also be transitioned to CRASHED.

    This simulates the scenario where a flow crashes due to infrastructure
    issues (e.g., OOM in Kubernetes) and ensures task runs don't remain
    stuck in RUNNING state.
    """
    async with get_client() as client:
        # Create a flow using the API
        flow_response = await client.request(
            "POST",
            "/flows/",
            json=FlowCreate(name="crash-test-flow").model_dump(mode="json"),
        )
        flow_id = flow_response.json()["id"]

        # Create flow run
        flow_run_response = await client.request(
            "POST",
            "/flow_runs/",
            json=FlowRunCreate(
                flow_id=flow_id,
                name="crash-test-run",
            ).model_dump(mode="json"),
        )
        flow_run_id = flow_run_response.json()["id"]

        # Set flow run to RUNNING
        await client.set_flow_run_state(UUID(flow_run_id), Running())

        # Create task runs in RUNNING state
        task_run_ids = []
        for i in range(3):
            task_run = await client.create_task_run(
                task=long_running_task,
                flow_run_id=UUID(flow_run_id),
                name=f"task-{i + 1}",
                dynamic_key=str(i),
            )
            task_run_ids.append(task_run.id)
            await client.set_task_run_state(task_run.id, Running())

        # Verify task states before crash
        task_runs_before = await client.read_task_runs(
            flow_run_filter=filters.FlowRunFilter(id={"any_": [UUID(flow_run_id)]})
        )
        for tr in task_runs_before:
            assert tr.state.type == StateType.RUNNING

        # Simulate a crash by setting flow run to CRASHED
        await client.set_flow_run_state(
            UUID(flow_run_id),
            Crashed(message="Simulated crash - process killed by OOM"),
        )

        # Check that all task runs are now CRASHED
        task_runs_after = await client.read_task_runs(
            flow_run_filter=filters.FlowRunFilter(id={"any_": [UUID(flow_run_id)]})
        )

        for tr in task_runs_after:
            assert tr.state.type == StateType.CRASHED, (
                f"Task {tr.name} should be CRASHED but is {tr.state.type}"
            )
            assert "parent flow run crashed" in tr.state.message.lower()
