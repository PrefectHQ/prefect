from typing import Callable, Dict
from urllib.parse import urlparse
from time import sleep

import requests

import prefect


class DatabricksRunTimeout(Exception):
    pass


class DatabricksJobsApiClient:
    """
    Class encapsulating interations with the Databricks 2.1 Jobs API
    """

    _user_agent_header = {"user-agent": f"prefect-{prefect.__version__}"}

    def __init__(self, host: str, token: str, timeout_seconds=180):
        self.host = self._parse_host(host)
        self.token = token
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _parse_host(host):
        """
        The purpose of this function is to be robust to improper connections
        settings provided by users, specifically in the host field.

        For example -- when users supply `https://xx.cloud.databricks.com` as the
        host, we must strip out the protocol to get the host.::

            h = DatabricksHook()
            assert h._parse_host('https://xx.cloud.databricks.com') == \
                'xx.cloud.databricks.com'

        In the case where users supply the correct ``xx.cloud.databricks.com`` as the
        host, this function is a no-op.::

            assert h._parse_host('xx.cloud.databricks.com') == 'xx.cloud.databricks.com'

        """
        urlparse_host = urlparse(host).hostname
        if urlparse_host:
            # In this case, host = https://xx.cloud.databricks.com
            return urlparse_host
        else:
            # In this case, host = xx.cloud.databricks.com
            return host

    def _perform_api_call(self, requests_method: Callable, endpoint: str, json: Dict):
        response = requests_method(
            url=f"https://{self.host}/{endpoint}",
            json=json,
            headers={
                **self.__class__._user_agent_header,
                "Authorization": f"Bearer {self.token}",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def run_now(self, json):
        response = self._perform_api_call(requests.post, "api/2.1/jobs/run-now", json)
        return response["run_id"]

    def submit_run(self, json):
        response = self._perform_api_call(
            requests.post, "api/2.1/jobs/runs/submit", json
        )
        return response["run_id"]

    def get_run(self, run_id: str):
        return self._perform_api_call(
            requests.get, "api/2.1/jobs/runs/get", {"run_id": run_id}
        )

    def cancel_run(self, run_id: str):
        self._perform_api_call(
            requests.post, "api/2.0/jobs/runs/cancel", {"run_id": run_id}
        )

    def wait_for_run_completion(
        self, run_id: str, max_wait_seconds: int = 300, polling_period_seconds: int = 30
    ):
        seconds_waited = 0
        life_cycle_state = None
        while seconds_waited < max_wait_seconds:
            run_info = self.get_run(run_id)
            state = run_info.get("state", {})
            life_cycle_state = state.get("life_cycle_state")

            if life_cycle_state in (
                "TERMINATED",
                "SKIPPED",
                "INTERNAL_ERROR",
            ):
                return state.get("result_state")

            sleep(polling_period_seconds)

        raise DatabricksRunTimeout()
