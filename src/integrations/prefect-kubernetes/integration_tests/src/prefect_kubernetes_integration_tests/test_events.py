import asyncio
import os
import subprocess
from typing import Any

import anyio
import pytest

from prefect import get_client
from prefect.states import StateType
from prefect_kubernetes_integration_tests.utils import display, prefect_core

DEFAULT_JOB_VARIABLES: dict[str, Any] = {
    "image": "prefecthq/prefect:3.2.11-python3.12",
}
if os.environ.get("CI", False):
    DEFAULT_JOB_VARIABLES["env"] = {"PREFECT_API_URL": "http://172.17.0.1:4200/api"}

DEFAULT_PARAMETERS = {"n": 5}
# Default source is a simple flow that sleeps
DEFAULT_FLOW_SOURCE = "https://gist.github.com/772d095672484b76da40a4e6158187f0.git"
DEFAULT_FLOW_ENTRYPOINT = "sleeping.py:sleepy"


@pytest.mark.usefixtures("kind_cluster")
async def test_happy_path_events(
    work_pool_name: str,
):
    """Test that we get the expected events when a flow run is successful."""
    flow_run = await prefect_core.create_flow_run(
        source=DEFAULT_FLOW_SOURCE,
        entrypoint=DEFAULT_FLOW_ENTRYPOINT,
        name="happy-path-pod-events",
        work_pool_name=work_pool_name,
        job_variables=DEFAULT_JOB_VARIABLES,
        parameters=DEFAULT_PARAMETERS,
        flow_run_name="happy-path-events",
    )

    display.print_flow_run_created(flow_run)

    with subprocess.Popen(
        ["prefect", "worker", "start", "--pool", work_pool_name],
    ) as worker_process:
        try:
            prefect_core.wait_for_flow_run_state(
                flow_run.id, StateType.COMPLETED, timeout=30
            )

            async with get_client() as client:
                updated_flow_run = await client.read_flow_run(flow_run.id)

            display.print_flow_run_result(updated_flow_run)

            # Collect events while worker is still running
            events = []
            with anyio.move_on_after(30):
                while len(events) < 3:
                    events = await prefect_core.read_pod_events_for_flow_run(
                        flow_run.id
                    )
                    await asyncio.sleep(1)
        finally:
            worker_process.terminate()

    assert len(events) == 3, (
        f"Expected 3 events, got {len(events)}: {[event.event for event in events]}"
    )
    assert {event.event for event in events} == {
        "prefect.kubernetes.pod.pending",
        "prefect.kubernetes.pod.running",
        "prefect.kubernetes.pod.succeeded",
    }, (
        f"Expected events to be Pending, Running, and Succeeded, got: {[event.event for event in events]}"
    )
