from concurrent.futures import ThreadPoolExecutor

from prefect_kubernetes_integration_tests.scenarios.base import BaseScenario
from prefect_kubernetes_integration_tests.utils import display, k8s, prefect_core
from rich.console import Console

from prefect import get_client
from prefect.states import StateType

console = Console()


class PodEvictionScenario(BaseScenario):
    """Test pod eviction handling."""

    name = "pod-eviction"
    description = "Tests that flow runs properly handle pod evictions"
    expected_state = StateType.CRASHED

    # Default source is a simple flow that sleeps
    flow_source = "https://gist.github.com/772d095672484b76da40a4e6158187f0.git"
    flow_entrypoint = "sleeping.py:sleepy"
    flow_name = "pod-eviction-test"

    async def execute(self) -> bool:
        """Execute the pod eviction scenario."""
        self.flow_run = await prefect_core.create_flow_run(
            source=self.flow_source,
            entrypoint=self.flow_entrypoint,
            name=self.flow_name,
            work_pool_name=self.work_pool_name,
        )

        display.print_flow_run_created(self.flow_run)

        with ThreadPoolExecutor(max_workers=1) as executor:
            worker_future = executor.submit(
                lambda: prefect_core.start_worker(self.work_pool_name, run_once=True)
            )

            try:
                self.job_name = k8s.get_job_name(self.flow_run.name)
                self.pod_name = k8s.wait_for_pod(self.job_name, timeout=120)

                k8s.evict_pod(self.pod_name)

            finally:
                worker_future.result()

            async with get_client() as client:
                updated_flow_run = await client.read_flow_run(self.flow_run.id)

                assert self.expected_state is not None
                return display.print_flow_run_result(
                    updated_flow_run, expected_state=self.expected_state
                )
