import asyncio
import os
import subprocess
from typing import Any

import anyio
import pytest

from prefect import get_client
from prefect.states import StateType
from prefect_kubernetes_integration_tests.utils import display, k8s, prefect_core

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
async def test_failed_pod_start(
    work_pool_name: str,
):
    """Test flow runs with pods that fail to start are marked as crashed."""
    flow_run = await prefect_core.create_flow_run(
        source=DEFAULT_FLOW_SOURCE,
        entrypoint=DEFAULT_FLOW_ENTRYPOINT,
        name="failed-pod-start",
        work_pool_name=work_pool_name,
        # Use an invalid image to ensure the pod will fail to start
        job_variables=DEFAULT_JOB_VARIABLES
        | {"image": "ceci-nest-pas-une-image:latest"},
        parameters=DEFAULT_PARAMETERS,
    )

    display.print_flow_run_created(flow_run)

    # Just use run_once here since we're looking for a crash detection
    prefect_core.start_worker(work_pool_name, run_once=True)

    # After worker finishes, verify the flow run reached CRASHED state
    prefect_core.wait_for_flow_run_state(flow_run.id, StateType.CRASHED, timeout=120)

    async with get_client() as client:
        updated_flow_run = await client.read_flow_run(flow_run.id)
    assert updated_flow_run.state is not None
    assert updated_flow_run.state.type == StateType.CRASHED

    display.print_flow_run_result(updated_flow_run)

    # Get events after worker has finished
    events = []
    with anyio.move_on_after(10):
        while len(events) < 1:
            events = await prefect_core.read_pod_events_for_flow_run(flow_run.id)
            await asyncio.sleep(1)

    assert len(events) == 1, "Expected 1 event"
    # Pod never fully starts, so we don't get a "running" or "succeeded" event
    assert {event.event for event in events} == {
        "prefect.kubernetes.pod.pending",
    }


@pytest.mark.usefixtures("kind_cluster")
async def test_backoff_limit_exhausted(
    work_pool_name: str,
):
    """Test flow runs with pods that exhaust their backoff limit are marked as crashed."""
    flow_run = await prefect_core.create_flow_run(
        source=DEFAULT_FLOW_SOURCE,
        entrypoint=DEFAULT_FLOW_ENTRYPOINT,
        name="backoff-limit-exhausted",
        work_pool_name=work_pool_name,
        # Use an invalid image to ensure the pod will fail to start
        job_variables=DEFAULT_JOB_VARIABLES | {"backoff_limit": 1},
    )

    display.print_flow_run_created(flow_run)

    with subprocess.Popen(
        ["prefect", "worker", "start", "--pool", work_pool_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as worker_process:
        try:
            job = k8s.get_job_for_flow_run(flow_run.name, timeout=120)
            # this loop is a bully
            while job.status and job.status.completion_time is None:
                try:
                    pod_name = k8s.wait_for_pod(job.metadata.name, timeout=15)
                except TimeoutError:
                    break
                # Should hit the backoff limit after final eviction
                k8s.evict_pod(pod_name)
                await asyncio.sleep(1)

            prefect_core.wait_for_flow_run_state(
                flow_run.id, StateType.CRASHED, timeout=60
            )

        finally:
            worker_process.terminate()

    async with get_client() as client:
        updated_flow_run = await client.read_flow_run(flow_run.id)

    assert updated_flow_run.state is not None
    assert updated_flow_run.state.type == StateType.CRASHED

    display.print_flow_run_result(updated_flow_run)

    events = []
    with anyio.move_on_after(10):
        while len(events) < 6:
            events = await prefect_core.read_pod_events_for_flow_run(flow_run.id)
            await asyncio.sleep(1)
    assert len(events) == 6, "Expected 6 events"
    # Pod never fully starts, so we don't get a "running" or "succeeded" event
    assert [event.event for event in events] == [
        "prefect.kubernetes.pod.failed",
        "prefect.kubernetes.pod.running",
        "prefect.kubernetes.pod.pending",
        "prefect.kubernetes.pod.failed",
        "prefect.kubernetes.pod.running",
        "prefect.kubernetes.pod.pending",
    ], "Expected events to be Pending, Running, Failed, and Succeeded"
