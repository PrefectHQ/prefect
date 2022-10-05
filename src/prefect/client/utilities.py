import time
from datetime import datetime

import pendulum

from prefect.client.orion import get_client, schemas
from prefect.utilities.asyncutils import sync_compatible


@sync_compatible
async def run_deployment(
    name: str,
    parameters: dict = None,
    scheduled_time: datetime = None,
    max_polls: int = 60,
    poll_interval: float = 5,
):
    """
    Runs a deployment immediately and returns a FlowRun object.

    This function will return when the created flow run enters a terminal state or until
    the polling duration has been exceeded.

    Args:
        name: The deployment name in the form: '<flow-name>/<deployment-name>'
        parameters: Parameter overrides for this flow run. Merged with the deployment
            defaults
        max_polls: The maximum number of times to poll the flow run before returning.
            Setting `max_polls` to 0 will return the FlowRun object immediately. Setting
            `max_polls` to -1 will allow this function to poll indefinitely.
    """
    if max_polls < -1:
        raise ValueError(
            "`max_polls` must be -1 (unlimited polling), 0 (return immediately) or any positive integer"
        )

    if scheduled_time is None:
        scheduled_time = pendulum.now("UTC")

    async with get_client() as client:
        deployment = await client.read_deployment_by_name(name)
        flow_run = await client.create_flow_run_from_deployment(
            deployment.id,
            state=schemas.states.Scheduled(scheduled_time=scheduled_time),
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
