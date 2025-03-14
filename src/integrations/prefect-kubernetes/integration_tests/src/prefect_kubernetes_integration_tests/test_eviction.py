import asyncio
import os
import subprocess
import time
from typing import Any

import anyio
import pytest
from rich.console import Console

from prefect import get_client
from prefect.states import StateType
from prefect_kubernetes_integration_tests.utils import display, k8s, prefect_core

console = Console()

DEFAULT_JOB_VARIABLES: dict[str, Any] = {"image": "prefecthq/prefect:3.2.11-python3.12"}
if os.environ.get("CI", False):
    DEFAULT_JOB_VARIABLES["env"] = {"PREFECT_API_URL": "http://172.17.0.1:4200/api"}
# Default source is a simple flow that sleeps
DEFAULT_FLOW_SOURCE = "https://gist.github.com/772d095672484b76da40a4e6158187f0.git"
DEFAULT_FLOW_ENTRYPOINT = "sleeping.py:sleepy"


@pytest.mark.usefixtures("kind_cluster")
async def test_default_pod_eviction(
    work_pool_name: str, capsys: pytest.CaptureFixture[str]
):
    """Test that flow runs properly handle pod evictions with the default configuration."""
    flow_run = await prefect_core.create_flow_run(
        source=DEFAULT_FLOW_SOURCE,
        entrypoint=DEFAULT_FLOW_ENTRYPOINT,
        name="default-pod-eviction",
        work_pool_name=work_pool_name,
        job_variables=DEFAULT_JOB_VARIABLES,
        flow_run_name="default-pod-eviction-test",
    )

    display.print_flow_run_created(flow_run)

    # Start a worker that runs continuously
    with subprocess.Popen(
        ["prefect", "worker", "start", "--pool", work_pool_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as worker_process:
        try:
            job_name = k8s.get_job_name(flow_run.name, timeout=120)
            # Try to wait for a running pod, but if we time out, continue with flow run state check
            pod_name = k8s.wait_for_pod(job_name, timeout=60)

            # Wait for the flow run to be running - this is more reliable than pod state
            prefect_core.wait_for_flow_run_state(flow_run.id, StateType.RUNNING)

            k8s.evict_pod(pod_name)

            # Give the worker time to process the eviction
            # The worker may keep the flow run in RUNNING while it observes the eviction, then mark it as SCHEDULED
            state_type = None
            start_time = time.time()
            timeout = 30

            # Wait for either SCHEDULED or COMPLETED state after eviction
            with console.status(
                f"Waiting for flow run {flow_run.id} to be rescheduled..."
            ):
                while time.time() - start_time < timeout:
                    state_type, _ = prefect_core.get_flow_run_state(flow_run.id)
                    if state_type in (StateType.SCHEDULED, StateType.COMPLETED):
                        break
                    time.sleep(1)

            # After eviction we need to give it time to start a new pod and let it finish
            # Skip the explicit wait for the pod to succeed since we're already checking
            # for the flow run state (which only happens when the pod succeeds)
            try:
                # Try to wait for the pod but don't fail the test if it times out
                k8s.wait_for_pod(job_name, phase="Succeeded", timeout=30)
            except TimeoutError:
                print(
                    "Couldn't find succeeded pod, but continuing since we care about events"
                )

            # Wait until we can capture the eviction message
            assert "evicted successfully" in capsys.readouterr().out

            async with get_client() as client:
                updated_flow_run = await client.read_flow_run(flow_run.id)

                display.print_flow_run_result(updated_flow_run)

                assert updated_flow_run.state is not None, (
                    "Flow run state should not be None"
                )
                assert updated_flow_run.state.type in (
                    StateType.SCHEDULED,
                    StateType.COMPLETED,
                ), (
                    "Expected flow run to be SCHEDULED or COMPLETED. Got "
                    f"{updated_flow_run.state.type} instead."
                )

                # Collect events while the worker is still running
                events = []
                with anyio.move_on_after(30):
                    while len(events) < 3:
                        events = await prefect_core.read_pod_events_for_flow_run(
                            flow_run.id
                        )
                        print(
                            f"Found {len(events)} events: {[event.event for event in events]}"
                        )
                        await asyncio.sleep(1)

                # Delete the flow run to avoid other tests from trying to use it
                await client.delete_flow_run(updated_flow_run.id)
        finally:
            worker_process.terminate()

    assert len(events) == 3, (
        f"Expected 3 events, got {len(events)}: {[event.event for event in events]}"
    )
    assert (
        {event.event for event in events}
        == {
            "prefect.kubernetes.pod.pending",
            "prefect.kubernetes.pod.running",
            "prefect.kubernetes.pod.succeeded",  # Will be succeed because the container will exit with 0 status code after rescheduling
        }
    ), (
        f"Expected events to be Pending, Running, and Succeeded, got: {[event.event for event in events]}"
    )


@pytest.mark.usefixtures("kind_cluster")
async def test_pod_eviction_with_backoff_limit(
    work_pool_name: str, capsys: pytest.CaptureFixture[str]
):
    """Test that flow runs properly handle pod evictions when the backoff limit is set."""
    flow_run = await prefect_core.create_flow_run(
        source=DEFAULT_FLOW_SOURCE,
        entrypoint=DEFAULT_FLOW_ENTRYPOINT,
        name="pod-eviction-with-backoff-limit",
        work_pool_name=work_pool_name,
        job_variables=DEFAULT_JOB_VARIABLES | {"backoff_limit": 6},
        # Set short sleep because we want this flow to finish after eviction
        parameters={"n": 10},
        flow_run_name="pod-eviction-test-backoff-limit",
    )

    display.print_flow_run_created(flow_run)

    # Start a worker that runs continuously
    with subprocess.Popen(
        ["prefect", "worker", "start", "--pool", work_pool_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as worker_process:
        try:
            job_name = k8s.get_job_name(flow_run.name, timeout=120)
            pod_name = k8s.wait_for_pod(job_name, timeout=60)

            # Wait for the flow run to be running - this is more reliable than pod state
            prefect_core.wait_for_flow_run_state(flow_run.id, StateType.RUNNING)

            k8s.evict_pod(pod_name)

            prefect_core.wait_for_flow_run_state(
                flow_run.id, StateType.COMPLETED, timeout=30
            )

            # After eviction we need to give it time to start a new pod and let it finish
            # Skip the explicit wait for the pod to succeed since we're already checking
            # for the flow run state (which only happens when the pod succeeds)
            try:
                # Try to wait for the pod but don't fail the test if it times out
                k8s.wait_for_pod(job_name, phase="Succeeded", timeout=30)
            except TimeoutError:
                print(
                    "Couldn't find succeeded pod, but continuing since we care about events"
                )

            # Wait until we can capture the eviction message
            assert "evicted successfully" in capsys.readouterr().out

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

                # Collect events while worker is still running
                events = []
                with anyio.move_on_after(30):
                    while len(events) < 6:
                        events = await prefect_core.read_pod_events_for_flow_run(
                            flow_run.id
                        )
                        print(
                            f"Found {len(events)} events: {[event.event for event in events]}"
                        )
                        await asyncio.sleep(1)
        finally:
            worker_process.terminate()

    assert len(events) == 6, (
        f"Expected 6 events, got {len(events)}: {[event.event for event in events]}"
    )
    # Events come back in reverse order of creation
    assert [event.event for event in events] == [
        "prefect.kubernetes.pod.succeeded",
        "prefect.kubernetes.pod.running",
        "prefect.kubernetes.pod.pending",
        "prefect.kubernetes.pod.failed",
        "prefect.kubernetes.pod.running",
        "prefect.kubernetes.pod.pending",
    ], (
        f"Expected events to be in the correct order, got: {[event.event for event in events]}"
    )
