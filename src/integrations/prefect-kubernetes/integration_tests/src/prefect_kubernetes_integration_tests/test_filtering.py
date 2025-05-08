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

DEFAULT_PARAMETERS = {"n": 1}
# Default source is a simple flow that sleeps
DEFAULT_FLOW_SOURCE = "https://gist.github.com/772d095672484b76da40a4e6158187f0.git"
DEFAULT_FLOW_ENTRYPOINT = "sleeping.py:sleepy"


@pytest.mark.usefixtures("kind_cluster")
async def test_filter_by_namespace(
    work_pool_name: str, monkeypatch: pytest.MonkeyPatch
):
    """Test that the observer doesn't emit events for flow runs in namespaces that are not watched."""
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_KUBERNETES_OBSERVER_NAMESPACES",
        "other-namespace,yet-another-namespace",
    )
    flow_run = await prefect_core.create_flow_run(
        source=DEFAULT_FLOW_SOURCE,
        entrypoint=DEFAULT_FLOW_ENTRYPOINT,
        name="filter-by-namespace",
        work_pool_name=work_pool_name,
        job_variables=DEFAULT_JOB_VARIABLES,
        parameters=DEFAULT_PARAMETERS,
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

    events = await prefect_core.read_pod_events_for_flow_run(flow_run.id)
    assert len(events) == 0, (
        f"Expected 0 events, got {len(events)}: {[event.event for event in events]}"
    )


@pytest.mark.usefixtures("kind_cluster")
async def test_filter_by_label(work_pool_name: str, monkeypatch: pytest.MonkeyPatch):
    """Test that the observer doesn't emit events for flow runs that don't match the label filter."""
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_KUBERNETES_OBSERVER_ADDITIONAL_LABEL_FILTERS",
        "prefect.io/deployment-id=not-real-deployment-id",
    )
    flow_run = await prefect_core.create_flow_run(
        source=DEFAULT_FLOW_SOURCE,
        entrypoint=DEFAULT_FLOW_ENTRYPOINT,
        name="filter-by-label",
        work_pool_name=work_pool_name,
        job_variables=DEFAULT_JOB_VARIABLES,
        parameters=DEFAULT_PARAMETERS,
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
        finally:
            worker_process.terminate()

    events = await prefect_core.read_pod_events_for_flow_run(flow_run.id)
    assert len(events) == 0, (
        f"Expected 0 events, got {len(events)}: {[event.event for event in events]}"
    )
