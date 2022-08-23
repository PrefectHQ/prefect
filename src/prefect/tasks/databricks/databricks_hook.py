import logging
from time import sleep
from urllib.parse import urlparse

import requests
from requests import exceptions as requests_exceptions
from requests.auth import AuthBase

import prefect
from prefect.exceptions import PrefectException

RESTART_CLUSTER_ENDPOINT = ("POST", "api/2.1/clusters/restart")

START_CLUSTER_ENDPOINT = ("POST", "api/2.1/clusters/start")

TERMINATE_CLUSTER_ENDPOINT = ("POST", "api/2.1/clusters/delete")

RUN_NOW_ENDPOINT = ("POST", "api/2.1/jobs/run-now")

SUBMIT_RUN_ENDPOINT = ("POST", "api/2.0/jobs/runs/submit")

SUBMIT_MULTI_TASK_RUN_ENDPOINT = ("POST", "api/2.1/jobs/runs/submit")

GET_RUN_ENDPOINT = ("GET", "api/2.1/jobs/runs/get")

CANCEL_RUN_ENDPOINT = ("POST", "api/2.1/jobs/runs/cancel")

USER_AGENT_HEADER = {"user-agent": "prefect-{v}".format(v=prefect.__version__)}

LIST_JOB_ENDPOINT = ("GET", "api/2.1/jobs/list")


class RunState:
    """
    Utility class for the run state concept of Databricks runs.
    """

    def __init__(self, life_cycle_state, result_state, state_message):
        self.life_cycle_state = life_cycle_state
        self.result_state = result_state
        self.state_message = state_message

    @property
    def is_terminal(self) -> bool:
        """True if the current state is a terminal state."""
        if self.life_cycle_state not in RUN_LIFE_CYCLE_STATES:
            raise PrefectException(
                (
                    "Unexpected life cycle state: {}: If the state has "
                    "been introduced recently, please check the Databricks user "
                    "guide for troubleshooting information"
                ).format(self.life_cycle_state)
            )
        return self.life_cycle_state in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR")

    @property
    def is_successful(self) -> bool:
        """True if the result state is SUCCESS"""
        return self.result_state == "SUCCESS"

    def __eq__(self, other):
        return (
            self.life_cycle_state == other.life_cycle_state
            and self.result_state == other.result_state
            and self.state_message == other.state_message
        )

    def __repr__(self):
        return str(self.__dict__)


# noinspection PyAbstractClass
class DatabricksHook:
    """
    Interact with Databricks.

    Args:
        - databricks_conn_id (dict): The name of the databricks connection to use.
        - timeout_seconds (int): The amount of time in seconds the requests library
            will wait before timing-out.
        - retry_limit (int): The number of times to retry the connection in case of
            service outages.
        - retry_delay (float): The number of seconds to wait between retries (it
            might be a floating point number).
    """

    def __init__(
        self,
        databricks_conn_id: dict,
        timeout_seconds=180,
        retry_limit=3,
        retry_delay=1.0,
    ):

        self.databricks_conn = databricks_conn_id
        self.timeout_seconds = timeout_seconds
        if retry_limit < 1:
            raise ValueError("Retry limit must be greater than equal to 1")
        self.retry_limit = retry_limit
        self.retry_delay = retry_delay

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

    def _do_api_call(self, endpoint_info, json):
        """
        Utility function to perform an API call with retries

        Args:
            - endpoint_info (tuple[string, string]): Tuple of method and endpoint.
            - json (dict): Parameters for this API call.

        Returns:

            dict: If the api call returns a OK status code,
                this function returns the response in JSON. Otherwise,
                we throw an PrefectException.
        """
        method, endpoint = endpoint_info

        if "token" in self.databricks_conn:
            logging.info("Using token auth. ")
            auth = _TokenAuth(self.databricks_conn["token"])
            host = self._parse_host(self.databricks_conn["host"])
        else:
            logging.info("Using basic auth. ")
            auth = (self.databricks_conn["login"], self.databricks_conn["password"])
            host = self.databricks_conn["host"]

        url = "https://{host}/{endpoint}".format(
            host=self._parse_host(host), endpoint=endpoint
        )

        if method == "GET":
            request_func = requests.get
        elif method == "POST":
            request_func = requests.post
        elif method == "PATCH":
            request_func = requests.patch
        else:
            raise PrefectException("Unexpected HTTP Method: " + method)

        attempt_num = 1
        while True:
            try:
                response = request_func(
                    url,
                    json=json,
                    auth=auth,
                    headers=USER_AGENT_HEADER,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                return response.json()
            except requests_exceptions.RequestException as e:
                if not _retryable_error(e):
                    # In this case, the user probably made a mistake.
                    # Don't retry.
                    raise PrefectException(
                        "Response: {0}, Status Code: {1}".format(
                            e.response.content, e.response.status_code
                        )
                    ) from e

                self._log_request_error(attempt_num, e)

            if attempt_num == self.retry_limit:
                raise PrefectException(
                    (
                        "API requests to Databricks failed {} times. " + "Giving up."
                    ).format(self.retry_limit)
                )

            attempt_num += 1
            sleep(self.retry_delay)

    def _log_request_error(self, attempt_num, error):
        logging.error(
            "Attempt %s API Request to Databricks failed with reason: %s",
            attempt_num,
            error,
        )

    def run_now(self, json):
        """
        Utility function to call the ``api/2.1/jobs/run-now`` endpoint.

        Args:
         - json (dict): The data used in the body of the request to the ``run-now`` endpoint.

        Returns:
            - str: the run_id as a string
        """
        response = self._do_api_call(RUN_NOW_ENDPOINT, json)
        return response["run_id"]

    def submit_run(self, json):
        """
        Utility function to call the ``api/2.0/jobs/runs/submit`` endpoint.

        Args:
            - json (dict): The data used in the body of the request to the ``submit`` endpoint.

        Returns:
            - str: the run_id as a string
        """
        response = self._do_api_call(SUBMIT_RUN_ENDPOINT, json)
        return response["run_id"]

    def submit_multi_task_run(self, json):
        """
        Utility function to call the ``api/2.1/jobs/runs/submit`` endpoint.

        Args:
            - json (dict): The data used in the body of the request to the ``submit`` endpoint.

        Returns:
            - str: the run_id as a string
        """
        response = self._do_api_call(SUBMIT_MULTI_TASK_RUN_ENDPOINT, json)
        return response["run_id"]

    def get_run_page_url(self, run_id: str) -> str:
        """
        Retrieves run_page_url.

        Args:
            - run_id (str): id of the run

        Returns
            - str: URL of the run page
        """
        json = {"run_id": run_id}
        response = self._do_api_call(GET_RUN_ENDPOINT, json)
        return response["run_page_url"]

    def get_job_id(self, run_id: str) -> str:
        """
        Retrieves job_id from run_id.

        Args:
            - run_id (str): id of the run

        Returns
            - str: Job id for given Databricks run
        """
        json = {"run_id": run_id}
        response = self._do_api_call(GET_RUN_ENDPOINT, json)
        return response["job_id"]

    def get_run_state(self, run_id: str) -> RunState:
        """
        Retrieves run state of the run.

        Args:
            - run_id (str): id of the run

        Returns
            - str: state of the run
        """
        json = {"run_id": run_id}
        response = self._do_api_call(GET_RUN_ENDPOINT, json)
        state = response["state"]
        life_cycle_state = state["life_cycle_state"]
        # result_state may not be in the state if not terminal
        result_state = state.get("result_state", None)
        state_message = state["state_message"]
        return RunState(life_cycle_state, result_state, state_message)

    def cancel_run(self, run_id: str) -> None:
        """
        Cancels the run.

        Args:
            - run_id (str): id of the run
        """
        json = {"run_id": run_id}
        self._do_api_call(CANCEL_RUN_ENDPOINT, json)

    def restart_cluster(self, json: dict) -> None:
        """
        Restarts the cluster.

        Args:
            - json (dict): json dictionary containing cluster specification.
        """
        self._do_api_call(RESTART_CLUSTER_ENDPOINT, json)

    def start_cluster(self, json: dict) -> None:
        """
        Starts the cluster.

        Args:
            - json (dict): json dictionary containing cluster specification.
        """
        self._do_api_call(START_CLUSTER_ENDPOINT, json)

    def terminate_cluster(self, json: dict) -> None:
        """
        Terminates the cluster.

        Args:
            - json (dict): json dictionary containing cluster specification.
        """
        self._do_api_call(TERMINATE_CLUSTER_ENDPOINT, json)

    def get_job_id_by_name(self, job_name: str, limit: int = 25) -> int:
        """
        Retrieves job_id from run_id.

        Args:
            - job_name (str): Name of the job.

        Returns
            - int: Job id for given Databricks job.
        """
        matching_jobs = []
        more_jobs_to_list = True
        list_api_offset = 0
        while more_jobs_to_list:
            response_payload = self._do_api_call(
                LIST_JOB_ENDPOINT, {"limit": limit, "offset": list_api_offset}
            )
            all_jobs = response_payload.get("jobs", [])
            for j in all_jobs:
                if j["settings"]["name"] == job_name:
                    matching_jobs.append(j)
            list_api_offset = list_api_offset + limit
            more_jobs_to_list = response_payload["has_more"]

        if len(matching_jobs) > 1:
            raise ValueError(
                f"Job with name '{job_name}' is duplicated. Please make sure job names "
                f"are unique in Databricks."
            )

        if not matching_jobs:
            raise ValueError(f"Job with name '{job_name}' not found")

        return matching_jobs[0]["job_id"]


def _retryable_error(exception):
    return (
        isinstance(
            exception,
            (requests_exceptions.ConnectionError, requests_exceptions.Timeout),
        )
        or exception.response is not None
        and exception.response.status_code >= 500
    )


RUN_LIFE_CYCLE_STATES = [
    "PENDING",
    "RUNNING",
    "TERMINATING",
    "TERMINATED",
    "SKIPPED",
    "INTERNAL_ERROR",
]


class _TokenAuth(AuthBase):
    """
    Helper class for requests Auth field. AuthBase requires you to implement the __call__
    magic function.
    """

    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["Authorization"] = "Bearer " + self.token
        return r
