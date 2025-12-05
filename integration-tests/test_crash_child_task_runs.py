"""
Test that child task runs are crashed when their parent flow run crashes.

This verifies the fix for https://github.com/PrefectHQ/prefect/issues/19594
where task runs would remain stuck in RUNNING state when their parent flow
run crashed (e.g., OOM killed in Kubernetes).

These tests use API-level setup to simulate the exact server state that occurs
when infrastructure crashes a flow (e.g., K8s OOM). This is appropriate because:
1. The fix is a server-side orchestration rule that runs when flow state changes
2. When infrastructure kills a process, the flow/tasks don't "run" - the server
   just sees state transitions from external systems
3. API-level testing lets us precisely control the state scenario we're testing
"""

from uuid import UUID

from prefect import get_client, task
from prefect.client.schemas import filters
from prefect.client.schemas.actions import FlowCreate, FlowRunCreate
from prefect.states import Completed, Crashed, Running, StateType


@task
def example_task(task_num: int):
    """Example task definition used for creating task runs."""
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
        # Create a flow via API (simulates a registered flow)
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
        flow_run_id = UUID(flow_run_response.json()["id"])

        # Set flow run to RUNNING (simulates flow execution starting)
        await client.set_flow_run_state(flow_run_id, Running())

        # Create task runs in RUNNING state (simulates tasks mid-execution)
        for i in range(3):
            task_run = await client.create_task_run(
                task=example_task,
                flow_run_id=flow_run_id,
                name=f"task-{i + 1}",
                dynamic_key=str(i),
            )
            await client.set_task_run_state(task_run.id, Running())

        # Verify task states before crash
        task_runs_before = await client.read_task_runs(
            flow_run_filter=filters.FlowRunFilter(id={"any_": [flow_run_id]})
        )
        assert len(task_runs_before) == 3
        for tr in task_runs_before:
            assert tr.state.type == StateType.RUNNING

        # Simulate infrastructure crash by setting flow run to CRASHED
        # This is what happens when K8s OOMs a pod - external systems mark
        # the flow as crashed, triggering our orchestration rule
        await client.set_flow_run_state(
            flow_run_id,
            Crashed(message="Simulated crash - process killed by OOM"),
        )

        # Verify all task runs are now CRASHED
        task_runs_after = await client.read_task_runs(
            flow_run_filter=filters.FlowRunFilter(id={"any_": [flow_run_id]})
        )

        for tr in task_runs_after:
            assert tr.state.type == StateType.CRASHED, (
                f"Task {tr.name} should be CRASHED but is {tr.state.type}"
            )
            assert "parent flow run crashed" in tr.state.message.lower()


async def test_does_not_crash_already_completed_tasks():
    """
    Tasks that have already completed should NOT be changed when
    the flow crashes. Only non-terminal tasks should be affected.
    """
    async with get_client() as client:
        # Create flow and flow run
        flow_response = await client.request(
            "POST",
            "/flows/",
            json=FlowCreate(name="partial-crash-test-flow").model_dump(mode="json"),
        )
        flow_id = flow_response.json()["id"]

        flow_run_response = await client.request(
            "POST",
            "/flow_runs/",
            json=FlowRunCreate(flow_id=flow_id, name="partial-crash-run").model_dump(
                mode="json"
            ),
        )
        flow_run_id = UUID(flow_run_response.json()["id"])
        await client.set_flow_run_state(flow_run_id, Running())

        # Create one COMPLETED task and one RUNNING task
        completed_task = await client.create_task_run(
            task=example_task,
            flow_run_id=flow_run_id,
            name="completed-task",
            dynamic_key="0",
        )
        await client.set_task_run_state(completed_task.id, Completed())

        running_task = await client.create_task_run(
            task=example_task,
            flow_run_id=flow_run_id,
            name="running-task",
            dynamic_key="1",
        )
        await client.set_task_run_state(running_task.id, Running())

        # Crash the flow
        await client.set_flow_run_state(flow_run_id, Crashed(message="Flow crashed"))

        # Check results
        task_runs = await client.read_task_runs(
            flow_run_filter=filters.FlowRunFilter(id={"any_": [flow_run_id]})
        )
        task_states = {tr.name: tr.state.type for tr in task_runs}

        # Completed task should remain COMPLETED
        assert task_states["completed-task"] == StateType.COMPLETED
        # Running task should now be CRASHED
        assert task_states["running-task"] == StateType.CRASHED


async def test_crash_propagates_to_pending_tasks():
    """
    Tasks in PENDING state (not yet started) should also be crashed
    when the flow crashes, as they will never get to run.
    """
    async with get_client() as client:
        # Create flow and flow run
        flow_response = await client.request(
            "POST",
            "/flows/",
            json=FlowCreate(name="pending-crash-test-flow").model_dump(mode="json"),
        )
        flow_id = flow_response.json()["id"]

        flow_run_response = await client.request(
            "POST",
            "/flow_runs/",
            json=FlowRunCreate(flow_id=flow_id, name="pending-crash-run").model_dump(
                mode="json"
            ),
        )
        flow_run_id = UUID(flow_run_response.json()["id"])
        await client.set_flow_run_state(flow_run_id, Running())

        # Create task run in PENDING state (task submitted but not yet running)
        pending_task = await client.create_task_run(
            task=example_task,
            flow_run_id=flow_run_id,
            name="pending-task",
            dynamic_key="0",
        )
        # Task runs start in PENDING state by default, no need to set state

        # Crash the flow
        await client.set_flow_run_state(
            flow_run_id, Crashed(message="Flow crashed before task could start")
        )

        # Pending task should now be CRASHED
        task_run = await client.read_task_run(pending_task.id)
        assert task_run.state.type == StateType.CRASHED
