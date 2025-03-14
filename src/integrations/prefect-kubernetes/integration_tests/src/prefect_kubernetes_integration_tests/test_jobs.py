from __future__ import annotations

import os
import subprocess
from typing import Any

import pytest

from prefect import get_client
from prefect.states import StateType
from prefect_kubernetes_integration_tests.utils import display, prefect_core

DEFAULT_JOB_VARIABLES: dict[str, Any] = {"image": "prefecthq/prefect:3.2.11-python3.12"}
if os.environ.get("CI", False):
    DEFAULT_JOB_VARIABLES["env"] = {"PREFECT_API_URL": "http://172.17.0.1:4200/api"}

DEFAULT_PARAMETERS = {"n": 5}  # Short sleep time for faster tests
# Default source is a simple flow that sleeps
DEFAULT_FLOW_SOURCE = "https://gist.github.com/772d095672484b76da40a4e6158187f0.git"
DEFAULT_FLOW_ENTRYPOINT = "sleeping.py:sleepy"
DEFAULT_FLOW_NAME = "job-state-test"


@pytest.mark.usefixtures("kind_cluster")
async def test_successful_job_completion(
    work_pool_name: str,
):
    """Test that jobs complete successfully and don't trigger state changes."""
    flow_run = await prefect_core.create_flow_run(
        source=DEFAULT_FLOW_SOURCE,
        entrypoint=DEFAULT_FLOW_ENTRYPOINT,
        name=DEFAULT_FLOW_NAME,
        work_pool_name=work_pool_name,
        job_variables=DEFAULT_JOB_VARIABLES,
        parameters=DEFAULT_PARAMETERS,
        flow_run_name="successful-job-completion",
    )

    display.print_flow_run_created(flow_run)

    # Start worker and wait for completion
    with subprocess.Popen(
        ["prefect", "worker", "start", "--pool", work_pool_name],
    ) as worker_process:
        try:
            # Wait for the flow run to complete
            prefect_core.wait_for_flow_run_state(
                flow_run.id, StateType.COMPLETED, timeout=30
            )

            async with get_client() as client:
                updated_flow_run = await client.read_flow_run(flow_run.id)

                assert updated_flow_run.state is not None, (
                    "Flow run state should not be None"
                )
                assert updated_flow_run.state.type == StateType.COMPLETED, (
                    "Expected flow run to be COMPLETED. Got "
                    f"{updated_flow_run.state.type} instead."
                )

                display.print_flow_run_result(updated_flow_run)
        finally:
            worker_process.terminate()
