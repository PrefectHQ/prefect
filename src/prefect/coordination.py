import time
from datetime import datetime

from httpx import Client

import prefect.settings
from prefect.orion.api.server import ORION_API_VERSION
from prefect.settings import PREFECT_API_KEY, PREFECT_API_URL

TERMINAL_STATE_STRINGS = {
    "FAILED",
    "COMPLETED",
    "CANCELLED",
    "CRASHED",
}


class InvalidOrionError(RuntimeError):
    """
    Raised when the Orion instance used is not compatible with a feature.
    """


class MissingFlowRunError(RuntimeError):
    """
    Raised when a specific Flow run could not found.
    """


class DeploymentTimeout(RuntimeError):
    """
    Raised when a deployment has not reached a terminal state within the specified time.
    """


def _validate_api_url(api_url):
    if api_url is None:
        raise InvalidOrionError(
            "Coordination utilities cannot be used with ephemeral Orion"
        )


def _minimal_client():
    api_url = PREFECT_API_URL.value()
    _validate_api_url(api_url)

    api_key = PREFECT_API_KEY.value()
    api_version = ORION_API_VERSION

    httpx_settings = dict()
    httpx_settings.setdefault("headers", dict())

    httpx_settings.setdefault("base_url", api_url)
    httpx_settings["headers"].setdefault("X-PREFECT-API-VERSION", api_version)

    if api_key:
        httpx_settings["headers"].setdefault("Authorization", f"Bearer {api_key}")

    return Client(**httpx_settings)


def run_deployment(deployment_name: str, max_polls: int = 60, poll_interval: float = 5):
    """
    Runs a deployment immediately.

    This function will block until the deployment run enters a terminal state or until
    the polling duration has been exceeded.
    """

    client = _minimal_client()

    flow_run_id = client.post(
        f"/deployments/name/{deployment_name}/schedule_now"
    ).json()

    for poll in range(max_polls):
        time.sleep(poll_interval)
        try:
            flow_state = client.get(f"/flow_runs/{flow_run_id}").json()["state"]["type"]
        except KeyError:
            raise MissingFlowRunError("Error polling flow run")

        if flow_state in TERMINAL_STATE_STRINGS:
            return

        raise DeploymentTimeout("Deployment did not reach a terminal state and might still be running.")


def schedule_deployment(deployment_name: str, schedule_time: datetime = None):
    """
    Schedules a single deployment run for the specified time.

    If no time is provided, the deployment will be scheduled to run immediately.
    """

    client = _minimal_client()

    body = {"schedule_time": schedule_time.isoformat()}

    res = client.post(
        f"/deployments/name/{deployment_name}/schedule_now", json=body,
    )
    return res.json()
