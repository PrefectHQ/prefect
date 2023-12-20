from uuid import UUID

import anyio

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas import FlowRun
from prefect.exceptions import FlowWaitTimeout


async def wait_for_flow_run(
    client: PrefectClient,
    flow_run_id: UUID,
    timeout: int = 10800,
    poll_interval: int = 5,
) -> FlowRun:
    """Waits for the prefect flow run to finish and returns the FlowRun

    Ars:
        flow_run_id: The flow run ID for the flow run to wait for.
        timeout: The timeout in seconds, by default 10800 (3 hours).
        poll_interval: The poll interval in seconds, by default 5.
    Returns:
        FlowRun: The finished flow run.
    Raises:
        prefect.exceptions.FlowWaitTimeout: If flow run goes over the timeout.
    """
    with anyio.move_on_after(timeout):
        while True:
            flow_run = await client.read_flow_run(flow_run_id)
            flow_state = flow_run.state
            if flow_state and flow_state.is_final():
                return flow_run
            await anyio.sleep(poll_interval)

    raise FlowWaitTimeout(
        f"FlowRun with ID {flow_run_id} is taking longer than {timeout} seconds"
    )
