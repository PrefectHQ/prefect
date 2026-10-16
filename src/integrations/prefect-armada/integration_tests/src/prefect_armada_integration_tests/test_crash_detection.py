import asyncio
from typing import Any

import anyio
from prefect_armada.utilities import parse_job_pid

from prefect import get_client
from prefect.states import StateType
from prefect_armada_integration_tests.utils import armada, display, prefect_core


async def test_rejected_job_submission(
    work_pool_name: str,
    job_variables: dict[str, Any],
):
    """Test flow runs whose jobs Armada refuses to accept are marked as crashed."""
    flow_run = await prefect_core.create_flow_run(
        name="rejected-job-submission",
        work_pool_name=work_pool_name,
        # Armada rejects containers whose requests differ from their limits
        job_variables=job_variables | {"cpu_request": "100m", "cpu_limit": "200m"},
    )

    display.print_flow_run_created(flow_run)

    with prefect_core.running_worker(work_pool_name):
        prefect_core.wait_for_flow_run_state(flow_run.id, StateType.CRASHED, timeout=60)

    async with get_client() as client:
        updated_flow_run = await client.read_flow_run(flow_run.id)

    display.print_flow_run_result(updated_flow_run)

    assert updated_flow_run.state is not None
    assert "Unable to submit Armada job" in (updated_flow_run.state.message or "")
    assert updated_flow_run.infrastructure_pid is None


async def test_failed_job_start(
    work_pool_name: str,
    job_variables: dict[str, Any],
):
    """Test flow runs with jobs that fail before the flow run starts are marked as crashed."""
    flow_run = await prefect_core.create_flow_run(
        name="failed-job-start",
        work_pool_name=work_pool_name,
        # Exit before the flow run can report any state of its own
        job_variables=job_variables | {"command": "python -c 'raise SystemExit(1)'"},
    )

    display.print_flow_run_created(flow_run)

    with prefect_core.running_worker(work_pool_name):
        # The observer gives a pending flow run a grace period to report its own
        # state before marking it as crashed.
        prefect_core.wait_for_flow_run_state(
            flow_run.id, StateType.CRASHED, timeout=180
        )

        events = []
        with anyio.move_on_after(30):
            while "prefect.armada.job.failed" not in {e.event for e in events}:
                events = await prefect_core.read_job_events_for_flow_run(flow_run.id)
                await asyncio.sleep(1)

    async with get_client() as client:
        updated_flow_run = await client.read_flow_run(flow_run.id)

    display.print_flow_run_result(updated_flow_run)

    assert updated_flow_run.infrastructure_pid is not None
    _, _, job_id = parse_job_pid(updated_flow_run.infrastructure_pid)
    assert updated_flow_run.state is not None
    assert f"Armada job {job_id} for this flow run failed" in (
        updated_flow_run.state.message or ""
    )

    event_types = [event.event for event in events]
    assert "prefect.armada.job.failed" in event_types, (
        f"Expected a 'failed' event, got: {event_types}"
    )


async def test_job_cancelled_in_armada(
    work_pool_name: str,
    job_variables: dict[str, Any],
):
    """Test running flow runs whose jobs are cancelled outside of Prefect are marked as crashed."""
    flow_run = await prefect_core.create_flow_run(
        name="job-cancelled-in-armada",
        work_pool_name=work_pool_name,
        job_variables=job_variables,
        # Long enough that the flow run cannot finish on its own
        parameters={"n": 600},
    )

    display.print_flow_run_created(flow_run)

    with prefect_core.running_worker(work_pool_name):
        prefect_core.wait_for_flow_run_state(
            flow_run.id, StateType.RUNNING, timeout=120
        )

        async with get_client() as client:
            running_flow_run = await client.read_flow_run(flow_run.id)
        assert running_flow_run.infrastructure_pid is not None
        queue, job_set_id, job_id = parse_job_pid(running_flow_run.infrastructure_pid)

        armada.cancel_job(queue, job_set_id, job_id)

        prefect_core.wait_for_flow_run_state(
            flow_run.id, StateType.CRASHED, timeout=120
        )

        events = []
        with anyio.move_on_after(60):
            while "prefect.armada.job.cancelled" not in {e.event for e in events}:
                events = await prefect_core.read_job_events_for_flow_run(flow_run.id)
                await asyncio.sleep(1)

    async with get_client() as client:
        updated_flow_run = await client.read_flow_run(flow_run.id)

    display.print_flow_run_result(updated_flow_run)

    event_types = [event.event for event in events]
    assert "prefect.armada.job.running" in event_types, "Missing running event"
    assert "prefect.armada.job.cancelled" in event_types, "Missing cancelled event"
