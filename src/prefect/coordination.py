import time
from httpx import Client

import prefect.settings
from prefect.orion.api.server import ORION_API_VERSION
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_REQUEST_TIMEOUT,
    PREFECT_API_URL,
    PREFECT_ORION_DATABASE_CONNECTION_URL,
)

TERMINAL_STATE_STRINGS = {
    "FAILED",
    "COMPLETED",
    "CANCELLED",
    "CRASHED",
}


def run_deployment(deployment_name: str):
    api_url = PREFECT_API_URL.value()
    api_key = PREFECT_API_KEY.value()
    api_version = ORION_API_VERSION

    httpx_settings = dict()
    httpx_settings.setdefault("headers", dict())

    httpx_settings.setdefault("base_url", api_url)
    httpx_settings["headers"].setdefault("X-PREFECT-API-VERSION", api_version)

    if api_key:
        httpx_settings["headers"].setdefault("Authorization", f"Bearer {api_key}")

    client = Client(**httpx_settings)

    flow_run_id = client.post(f"/deployments/name/{deployment_name}/schedule_now").json()

    max_polls = 60
    for poll in range(60):
        time.sleep(5)
        flow_state = client.get(f"/flow_runs/{flow_run_id}").json()['state']['type']
        if flow_state in TERMINAL_STATE_STRINGS:
            break
