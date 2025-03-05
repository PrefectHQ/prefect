from concurrent.futures import ThreadPoolExecutor

import pytest

from prefect import get_client
from prefect.states import StateType
from prefect_kubernetes_integration_tests.utils import display, k8s, prefect_core


@pytest.mark.usefixtures("kind_cluster")
async def test_pod_eviction(work_pool_name: str, capsys: pytest.CaptureFixture[str]):
    """Test that flow runs properly handle pod evictions."""
    # Default source is a simple flow that sleeps
    flow_source = "https://gist.github.com/772d095672484b76da40a4e6158187f0.git"
    flow_entrypoint = "sleeping.py:sleepy"
    flow_name = "pod-eviction-test"

    flow_run = await prefect_core.create_flow_run(
        source=flow_source,
        entrypoint=flow_entrypoint,
        name=flow_name,
        work_pool_name=work_pool_name,
        job_variables={"image": "prefecthq/prefect:3-latest"},
    )

    display.print_flow_run_created(flow_run)

    with ThreadPoolExecutor(max_workers=1) as executor:
        worker_future = executor.submit(
            lambda: prefect_core.start_worker(work_pool_name, run_once=True)
        )

        try:
            job_name = k8s.get_job_name(flow_run.name, timeout=120)
            pod_name = k8s.wait_for_pod(job_name, timeout=120)

            k8s.evict_pod(pod_name)

        finally:
            worker_future.result()

        assert "evicted successfully" in capsys.readouterr().out

        async with get_client() as client:
            updated_flow_run = await client.read_flow_run(flow_run.id)

            assert updated_flow_run.state is not None, (
                "Flow run state should not be None"
            )
            assert updated_flow_run.state.type == StateType.CRASHED, (
                f"Expected flow run state to be CRASHED, got {updated_flow_run.state.type}"
            )

            display.print_flow_run_result(updated_flow_run)
