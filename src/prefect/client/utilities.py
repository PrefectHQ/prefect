import time
from datetime import datetime

import pendulum

from prefect.exceptions import PrefectHTTPStatusError
from prefect.client.orion import get_client
from prefect.utilities.asyncutils import sync_compatible


class MissingFlowRunError(RuntimeError):
    """
    Raised when a specific Flow run could not found.
    """


class DeploymentTimeout(RuntimeError):
    """
    Raised when a deployment has not reached a terminal state within the specified time.
    """


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

    async with get_client() as client:
        deployment = await client.read_deployment_by_name(name)
        flow_run = await client.create_flow_run_from_deployment(
            deployment.id,
            parameters=parameters,
        )

        flow_run_id = flow_run.id

        for poll in range(max_polls):
            time.sleep(poll_interval)
            try:
                flow_run = await client.read_flow_run(flow_run_id)
                flow_state = flow_run.state
            except PrefectHTTPStatusError:
                raise MissingFlowRunError("Error polling flow run")

            if flow_state and flow_state.is_final():
                return flow_state

        raise DeploymentTimeout(
            f"Deployment run did not terminate and is in the {flow_state} state"
        )
