import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest

from prefect import get_client
from prefect.states import StateType
from prefect_kubernetes_integration_tests.utils import display, k8s, prefect_core

DEFAULT_JOB_VARIABLES = {
    "image": "prefecthq/prefect:3.2.11-python3.12",
    "env": {"PREFECT_API_URL": "http://172.17.0.1:4200/api"},
}
# Default source is a simple flow that sleeps
DEFAULT_FLOW_SOURCE = "https://gist.github.com/772d095672484b76da40a4e6158187f0.git"
DEFAULT_FLOW_ENTRYPOINT = "sleeping.py:sleepy"
DEFAULT_FLOW_NAME = "pod-eviction-test"


@pytest.mark.usefixtures("kind_cluster")
async def test_default_pod_eviction(
    work_pool_name: str, capsys: pytest.CaptureFixture[str]
):
    """Test that flow runs properly handle pod evictions."""
    flow_run = await prefect_core.create_flow_run(
        source=DEFAULT_FLOW_SOURCE,
        entrypoint=DEFAULT_FLOW_ENTRYPOINT,
        name=DEFAULT_FLOW_NAME,
        work_pool_name=work_pool_name,
        job_variables=DEFAULT_JOB_VARIABLES,
    )

    display.print_flow_run_created(flow_run)

    with ThreadPoolExecutor(max_workers=1) as executor:
        worker_future = executor.submit(
            lambda: prefect_core.start_worker(work_pool_name, run_once=True)
        )

        try:
            job_name = k8s.get_job_name(flow_run.name, timeout=120)
            pod_name = k8s.wait_for_pod(job_name, timeout=120)
            # Wait for the flow run to be running
            prefect_core.wait_for_flow_run_state(flow_run.id, StateType.RUNNING)

            k8s.evict_pod(pod_name)

        finally:
            worker_future.result()

        assert "evicted successfully" in capsys.readouterr().out

        async with get_client() as client:
            updated_flow_run = await client.read_flow_run(flow_run.id)

            assert updated_flow_run.state is not None, (
                "Flow run state should not be None"
            )
            assert updated_flow_run.state.type != StateType.CRASHED, (
                "Expected flow run not be marked as CRASHED, but it was"
            )
            assert updated_flow_run.state.type == StateType.SCHEDULED, (
                "Expected flow run to be SCHEDULED. Got "
                f"{updated_flow_run.state.type} instead."
            )

            display.print_flow_run_result(updated_flow_run)


@pytest.mark.usefixtures("kind_cluster")
async def test_pod_eviction_with_backoff_limit(
    work_pool_name: str, capsys: pytest.CaptureFixture[str]
):
    """Test that flow runs properly handle pod evictions."""
    flow_run = await prefect_core.create_flow_run(
        source=DEFAULT_FLOW_SOURCE,
        entrypoint=DEFAULT_FLOW_ENTRYPOINT,
        name=DEFAULT_FLOW_NAME,
        work_pool_name=work_pool_name,
        job_variables=DEFAULT_JOB_VARIABLES | {"backoff_limit": 6},
        # Set short sleep because we want this flow to finish after eviction
        parameters={"n": 10},
    )

    display.print_flow_run_created(flow_run)

    with subprocess.Popen(
        ["prefect", "worker", "start", "--pool", work_pool_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as worker_process:
        try:
            job_name = k8s.get_job_name(flow_run.name, timeout=120)
            pod_name = k8s.wait_for_pod(job_name, timeout=120)
            # Wait for the flow run to be running
            prefect_core.wait_for_flow_run_state(flow_run.id, StateType.RUNNING)

            k8s.evict_pod(pod_name)

            prefect_core.wait_for_flow_run_state(
                flow_run.id, StateType.COMPLETED, timeout=30
            )

        finally:
            worker_process.terminate()

    assert "evicted successfully" in capsys.readouterr().out

    async with get_client() as client:
        updated_flow_run = await client.read_flow_run(flow_run.id)

        assert updated_flow_run.state is not None, "Flow run state should not be None"
        assert updated_flow_run.state.type != StateType.CRASHED, (
            "Expected flow run not be marked as CRASHED, but it was"
        )
        assert updated_flow_run.state.type == StateType.COMPLETED, (
            "Expected flow run to be COMPLETED. Got "
            f"{updated_flow_run.state.type} instead."
        )

        display.print_flow_run_result(updated_flow_run)
