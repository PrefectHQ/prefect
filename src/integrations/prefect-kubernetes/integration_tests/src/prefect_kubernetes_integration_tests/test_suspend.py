import asyncio
import os
import subprocess
from typing import Any

import pytest

from prefect import get_client
from prefect.states import StateType, Suspended
from prefect_kubernetes_integration_tests.utils import display, k8s, prefect_core

DEFAULT_JOB_VARIABLES: dict[str, Any] = {
    "image": "prefecthq/prefect:3.2.11-python3.12",
}
if os.environ.get("CI", False):
    DEFAULT_JOB_VARIABLES["env"] = {"PREFECT_API_URL": "http://172.17.0.1:4200/api"}

DEFAULT_FLOW_SOURCE = "https://gist.github.com/772d095672484b76da40a4e6158187f0.git"
DEFAULT_FLOW_ENTRYPOINT = "sleeping.py:sleepy"


@pytest.mark.usefixtures("kind_cluster")
async def test_suspended_flow_not_crashed_by_observer(
    work_pool_name: str,
):
    """Test that suspended flow runs are not marked as crashed when their K8s job fails.

    This verifies the observer correctly skips paused/suspended flow runs
    instead of incorrectly marking them as crashed.
    """
    flow_run = await prefect_core.create_flow_run(
        source=DEFAULT_FLOW_SOURCE,
        entrypoint=DEFAULT_FLOW_ENTRYPOINT,
        name="suspend-no-crash",
        work_pool_name=work_pool_name,
        job_variables=DEFAULT_JOB_VARIABLES | {"backoff_limit": 1},
        parameters={"n": 300},
        flow_run_name="suspend-no-crash-test",
    )

    display.print_flow_run_created(flow_run)

    with subprocess.Popen(
        ["prefect", "worker", "start", "--pool", work_pool_name],
    ) as worker_process:
        try:
            prefect_core.wait_for_flow_run_state(
                flow_run.id, StateType.RUNNING, timeout=120
            )

            async with get_client() as client:
                await client.set_flow_run_state(
                    flow_run.id, Suspended(timeout_seconds=300), force=True
                )

            state_type, _ = prefect_core.get_flow_run_state(flow_run.id)
            assert state_type == StateType.PAUSED, (
                f"Expected flow run to be PAUSED after suspend, got {state_type}"
            )

            job = k8s.get_job_for_flow_run(flow_run.name, timeout=30)
            while job.status and job.status.completion_time is None:
                try:
                    pod_name = k8s.wait_for_pod(job.metadata.name, timeout=15)
                except TimeoutError:
                    break
                k8s.evict_pod(pod_name)
                await asyncio.sleep(1)

            await asyncio.sleep(15)

            state_type, message = prefect_core.get_flow_run_state(flow_run.id)
            assert state_type == StateType.PAUSED, (
                f"Expected flow run to remain PAUSED after K8s job failure, "
                f"but got {state_type}: {message}"
            )

            async with get_client() as client:
                await client.resume_flow_run(flow_run.id)

            prefect_core.wait_for_flow_run_state(
                flow_run.id, StateType.SCHEDULED, timeout=30
            )

        finally:
            worker_process.terminate()

    async with get_client() as client:
        updated_flow_run = await client.read_flow_run(flow_run.id)
    display.print_flow_run_result(updated_flow_run)
