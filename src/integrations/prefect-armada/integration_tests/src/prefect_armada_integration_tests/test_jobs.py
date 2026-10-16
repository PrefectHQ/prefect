from __future__ import annotations

from typing import Any

from armada_client.typings import JobState
from prefect_armada.utilities import parse_job_pid

from prefect import get_client
from prefect.states import StateType
from prefect_armada_integration_tests.utils import armada, display, prefect_core

DEFAULT_PARAMETERS = {"n": 5}  # Short sleep time for faster tests


async def test_successful_job_completion(
    work_pool_name: str,
    armada_queue: str,
    job_variables: dict[str, Any],
):
    """Test that a flow run executes as an Armada job and runs to completion."""
    flow_run = await prefect_core.create_flow_run(
        name="job-state-test",
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

    assert updated_flow_run.infrastructure_pid is not None
    queue, job_set_id, job_id = parse_job_pid(updated_flow_run.infrastructure_pid)
    assert queue == armada_queue
    # Each flow run is submitted to its own job set
    assert job_set_id.endswith(str(flow_run.id))

    armada.wait_for_job_state(job_id, JobState.SUCCEEDED, timeout=30)
