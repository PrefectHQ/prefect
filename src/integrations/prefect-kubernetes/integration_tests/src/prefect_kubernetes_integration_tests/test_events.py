import asyncio

import anyio
import pytest

from prefect import get_client
from prefect.states import StateType
from prefect_kubernetes_integration_tests.utils import display, prefect_core

DEFAULT_JOB_VARIABLES = {
    "image": "prefecthq/prefect:3.2.11-python3.12",
    "env": {"PREFECT_API_URL": "http://172.17.0.1:4200/api"},
}
DEFAULT_PARAMETERS = {"n": 5}
# Default source is a simple flow that sleeps
DEFAULT_FLOW_SOURCE = "https://gist.github.com/772d095672484b76da40a4e6158187f0.git"
DEFAULT_FLOW_ENTRYPOINT = "sleeping.py:sleepy"
DEFAULT_FLOW_NAME = "pod-eviction-test"


@pytest.mark.usefixtures("kind_cluster")
async def test_happy_path_events(
    work_pool_name: str,
):
    """Test that flow runs properly handle pod evictions."""
    flow_run = await prefect_core.create_flow_run(
        source=DEFAULT_FLOW_SOURCE,
        entrypoint=DEFAULT_FLOW_ENTRYPOINT,
        name=DEFAULT_FLOW_NAME,
        work_pool_name=work_pool_name,
        job_variables=DEFAULT_JOB_VARIABLES,
        parameters=DEFAULT_PARAMETERS,
    )

    display.print_flow_run_created(flow_run)

    prefect_core.start_worker(work_pool_name, run_once=True)

    async with get_client() as client:
        updated_flow_run = await client.read_flow_run(flow_run.id)

        assert updated_flow_run.state is not None, "Flow run state should not be None"
        assert updated_flow_run.state.type == StateType.COMPLETED, (
            "Expected flow run to be COMPLETED. Got "
            f"{updated_flow_run.state.type} instead."
        )

        display.print_flow_run_result(updated_flow_run)

    events = []
    with anyio.move_on_after(10):
        while len(events) < 3:
            events = await prefect_core.read_pod_events_for_flow_run(flow_run.id)
            await asyncio.sleep(1)
    assert len(events) == 3, "Expected 3 events"
