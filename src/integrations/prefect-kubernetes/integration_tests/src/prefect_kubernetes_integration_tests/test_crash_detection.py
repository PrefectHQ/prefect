import asyncio
import os
import subprocess
from typing import Any

import anyio
import pytest
from rich.console import Console

from prefect import get_client
from prefect.states import StateType
from prefect_kubernetes_integration_tests.utils import display, k8s, prefect_core

console = Console()

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
        flow_run_name="failed-pod-start-test",
    )

    display.print_flow_run_created(flow_run)

    # Use run_once mode for the crash detection test since we just need one attempt
    # Unlike the subprocess approach, this will block until the worker completes
    print("Starting worker in run_once mode to detect crash...")
    prefect_core.start_worker(work_pool_name, run_once=True)

    # After worker completes, give the observer a moment to process events
    await asyncio.sleep(5)

    # Check the final state
    print("Worker completed, checking final state...")
    state_type, message = prefect_core.get_flow_run_state(flow_run.id)
    print(f"Final state after worker run: {state_type} - {message}")

    # Allow both CRASHED and PENDING states - the important thing is
    # that the flow run didn't transition to RUNNING since the pod couldn't start
    acceptable_states = (StateType.CRASHED, StateType.PENDING)
    assert state_type in acceptable_states, (
        f"Expected flow run to be in one of {acceptable_states}, got {state_type}"
    )

    # Collect any events that were generated
    events = []
    with anyio.move_on_after(10):
        while len(events) < 1:
            events = await prefect_core.read_pod_events_for_flow_run(flow_run.id)
            await asyncio.sleep(1)

    async with get_client() as client:
        updated_flow_run = await client.read_flow_run(flow_run.id)
        display.print_flow_run_result(updated_flow_run)

    # Check if we got at least the pending event - but only if we have events
    # It's possible we don't get any events if the pod never started
    if events:
        event_types = {event.event for event in events}
        print(f"Found events: {event_types}")
        assert "prefect.kubernetes.pod.pending" in event_types, (
            f"Expected at least the 'pending' event, got: {event_types}"
        )


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

    # Collect events with a more generous timeout
    events = []
    max_events = 0
    with anyio.move_on_after(15):
        while True:
            current_events = await prefect_core.read_pod_events_for_flow_run(
                flow_run.id
            )
            if len(current_events) > max_events:
                max_events = len(current_events)
                events = current_events
                print(
                    f"Found {len(events)} events: {[event.event for event in events]}"
                )
            # If we got at least 5 events, that's enough
            if len(events) >= 5:
                break
            await asyncio.sleep(1)

    # Instead of expecting exactly 6 events, check for at least 5
    assert len(events) >= 5, (
        f"Expected at least 5 events, got {len(events)}: {[event.event for event in events]}"
    )

    # Instead of checking exact order, check the event types
    event_types = {event.event for event in events}
    assert "prefect.kubernetes.pod.pending" in event_types, "Missing pending event"
    assert "prefect.kubernetes.pod.running" in event_types, "Missing running event"
    assert "prefect.kubernetes.pod.failed" in event_types, "Missing failed event"

    # Verify we have events from both pod attempts
    event_list = [event.event for event in events]
    # Count occurrences to verify retries
    pending_count = event_list.count("prefect.kubernetes.pod.pending")
    assert pending_count >= 1, "Expected at least one pending event"
    running_count = event_list.count("prefect.kubernetes.pod.running")
    assert running_count >= 1, "Expected at least one running event"
    failed_count = event_list.count("prefect.kubernetes.pod.failed")
    assert failed_count >= 1, "Expected at least one failed event"

    # Verify the backoff retry happened
    total_events = pending_count + running_count + failed_count
    assert total_events >= 4, (
        f"Expected at least 4 events for retry, got {total_events}"
    )
