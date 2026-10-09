import asyncio
import os
from typing import Any

import anyio

from prefect import get_client
from prefect.states import StateType
from prefect_armada_integration_tests.utils import display, prefect_core

DEFAULT_PARAMETERS = {"n": 5}


async def test_happy_path_events(
    work_pool_name: str,
    job_variables: dict[str, Any],
):
    """Test that we get the expected events when a flow run is successful."""
    flow_run = await prefect_core.create_flow_run(
        name="happy-path-job-events",
        work_pool_name=work_pool_name,
        job_variables=job_variables,
        parameters=DEFAULT_PARAMETERS,
    )

    display.print_flow_run_created(flow_run)

    with prefect_core.running_worker(work_pool_name):
        prefect_core.wait_for_flow_run_state(
            flow_run.id, StateType.COMPLETED, timeout=120
        )

        async with get_client() as client:
            updated_flow_run = await client.read_flow_run(flow_run.id)

        display.print_flow_run_result(updated_flow_run)

        # Collect events while worker is still running
        events = []
        with anyio.move_on_after(30):
            while "prefect.armada.job.succeeded" not in {e.event for e in events}:
                events = await prefect_core.read_job_events_for_flow_run(flow_run.id)
                await asyncio.sleep(1)

    event_types = [event.event for event in events]
    # Armada reports more of a job's lifecycle than this, such as its lease by
    # an executor, but these are the events every successful job produces.
    assert {
        "prefect.armada.job.submitted",
        "prefect.armada.job.queued",
        "prefect.armada.job.running",
        "prefect.armada.job.succeeded",
    } <= set(event_types), f"Missing expected events, got: {event_types}"
    assert len(event_types) == len(set(event_types)), (
        f"Expected each event to be replicated once, got: {event_types}"
    )

    assert updated_flow_run.infrastructure_pid is not None
    job_id = updated_flow_run.infrastructure_pid.split(":")[-1]
    assert {event.resource.id for event in events} == {f"prefect.armada.job.{job_id}"}


async def test_disable_job_event_replication(
    work_pool_name: str,
    job_variables: dict[str, Any],
):
    """Test that job events are not replicated when disabled via settings."""
    flow_run = await prefect_core.create_flow_run(
        name="disabled-events",
        work_pool_name=work_pool_name,
        job_variables=job_variables,
        parameters=DEFAULT_PARAMETERS,
    )

    display.print_flow_run_created(flow_run)

    # Start worker with job event replication disabled
    env = os.environ.copy()
    env["PREFECT_INTEGRATIONS_ARMADA_OBSERVER_REPLICATE_JOB_EVENTS"] = "false"

    with prefect_core.running_worker(work_pool_name, env=env):
        prefect_core.wait_for_flow_run_state(
            flow_run.id, StateType.COMPLETED, timeout=120
        )

        async with get_client() as client:
            updated_flow_run = await client.read_flow_run(flow_run.id)

        display.print_flow_run_result(updated_flow_run)

        # Wait for any potential events to be sent (if they were going to be)
        await asyncio.sleep(15)
        events = await prefect_core.read_job_events_for_flow_run(flow_run.id)

    assert len(events) == 0, (
        f"Expected 0 events, got {len(events)}: {[event.event for event in events]}"
    )
