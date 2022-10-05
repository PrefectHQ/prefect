import time

from prefect.client.orion import get_client
from prefect.utilities.asyncutils import sync_compatible


@sync_compatible
async def run_deployment(
    name: str,
    max_polls: int = 60,
    poll_interval: float = 5,
    parameters: dict = None,
):
    """
    Runs a deployment immediately.

    This function will block until the deployment run enters a terminal state or until
    the polling duration has been exceeded.
    """
    if max_polls < -1:
        raise ValueError(
            "`max_polls` must be -1 (unlimited polling), 0 (return immediately) or any positive integer"
        )

    async with get_client() as client:
        deployment = await client.read_deployment_by_name(name)
        flow_run = await client.create_flow_run_from_deployment(
            deployment.id,
            parameters=parameters,
        )

        flow_run_id = flow_run.id

        polls = 0
        while max_polls == -1 or polls < max_polls:
            time.sleep(poll_interval)
            flow_run = await client.read_flow_run(flow_run_id)
            flow_state = flow_run.state
            polls += 1

            if flow_state and flow_state.is_final():
                return flow_run

        return flow_run
