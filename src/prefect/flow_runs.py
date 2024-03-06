from typing import Optional
from uuid import UUID

import anyio

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas import FlowRun
from prefect.client.utilities import inject_client
from prefect.exceptions import FlowRunWaitTimeout
from prefect.logging import get_logger


@inject_client
async def wait_for_flow_run(
    flow_run_id: UUID,
    timeout: Optional[int] = 10800,
    poll_interval: int = 5,
    client: Optional[PrefectClient] = None,
    log_states: bool = False,
) -> FlowRun:
    """
    Waits for the prefect flow run to finish and returns the FlowRun

    Args:
        flow_run_id: The flow run ID for the flow run to wait for.
        timeout: The wait timeout in seconds. Defaults to 10800 (3 hours).
        poll_interval: The poll interval in seconds. Defaults to 5.

    Returns:
        FlowRun: The finished flow run.

    Raises:
        prefect.exceptions.FlowWaitTimeout: If flow run goes over the timeout.

    Examples:
        Create a flow run for a deployment and wait for it to finish:
            ```python
            import asyncio

            from prefect import get_client
            from prefect.flow_runs import wait_for_flow_run

            async def main():
                async with get_client() as client:
                    flow_run = await client.create_flow_run_from_deployment(deployment_id="my-deployment-id")
                    flow_run = await wait_for_flow_run(flow_run_id=flow_run.id)
                    print(flow_run.state)

            if __name__ == "__main__":
                asyncio.run(main())

            ```

        Trigger multiple flow runs and wait for them to finish:
            ```python
            import asyncio

            from prefect import get_client
            from prefect.flow_runs import wait_for_flow_run

            async def main(num_runs: int):
                async with get_client() as client:
                    flow_runs = [
                        await client.create_flow_run_from_deployment(deployment_id="my-deployment-id")
                        for _
                        in range(num_runs)
                    ]
                    coros = [wait_for_flow_run(flow_run_id=flow_run.id) for flow_run in flow_runs]
                    finished_flow_runs = await asyncio.gather(*coros)
                    print([flow_run.state for flow_run in finished_flow_runs])

            if __name__ == "__main__":
                asyncio.run(main(num_runs=10))

            ```
    """
    assert client is not None, "Client injection failed"
    logger = get_logger()
    with anyio.move_on_after(timeout):
        while True:
            flow_run = await client.read_flow_run(flow_run_id)
            flow_state = flow_run.state
            if log_states:
                logger.info(f"Flow run is in state {flow_run.state.name!r}")
            if flow_state and flow_state.is_final():
                return flow_run
            await anyio.sleep(poll_interval)
    raise FlowRunWaitTimeout(
        f"Flow run with ID {flow_run_id} exceeded watch timeout of {timeout} seconds"
    )
