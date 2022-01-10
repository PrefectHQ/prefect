from typing import Callable, Dict
import requests
import prefect


class DatabricksJobsApiClient:
    """
    Class encapsulating interations with the Databricks 2.1 Jobs API
    """

    _user_agent_header = {"user-agent": f"prefect-{prefect.__version__}"}

    def __init__(self, host: str, token: str, timeout_seconds=180):
        self.host = host
        self.token = token
        self.timeout_seconds = timeout_seconds

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
