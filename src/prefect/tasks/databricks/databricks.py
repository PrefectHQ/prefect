import requests
from time import sleep, time
from prefect import Task, __version__


DATABRICKS_API_VERSION = "2.0"

USER_AGENT = f"Prefect-{__version__}"

DATABRICKS_JOB_STATUS = {"SUCCESS", "FAILED", "TIMEDOUT", "CANCELED"}


class DatabricksRunSubmit(Task):
    """
    Submit a Databricks one-time run

    Args:
        - databricks_token: Databricks secret token
        - databricks_host: Databricks shard host
        - spark_jar_task: Indicates that this job should run a JAR.
        - notebook_task: Indicates that this job should run a notebook.
                         This field may not be specified in conjunction with spark_jar_task.
        - spark_python_task: Indicates that this job should run a Python file.
        - spark_submit_task: Indicates that this job should run spark submit script
        - new_cluster: A description of a cluster that will be created for each run.
        - existing_cluster_id: The ID of an existing cluster that will be used for all runs of this job
        - libraries: An optional list of libraries to be installed on the cluster
        - timeout_seconds: An optional timeout applied to each run of this job, default is no timeout
        - databricks_retry_limit: Limit the number of retry to call the submit endpoint
        - databricks_retry_delay: Delay in seconds between two retries
        - polling_period: Delay in seconds between two consecutive GET call
        - polling_timeout: Timeout when unable to fetch a run state in the imparted time frame,
                           must be extended for long running task
        - **kwargs: additional arguments
    """

    def __init__(
        self,
        databricks_token=None,
        databricks_host=None,
        spark_jar_task=None,
        notebook_task=None,
        spark_python_task=None,
        spark_submit_task=None,
        new_cluster=None,
        existing_cluster_id=None,
        existing_cluster_name=None,
        libraries=None,
        timeout_seconds=10,
        databricks_retry_limit=3,
        databricks_retry_delay=1,
        polling_period=5,
        polling_timeout=3600,
        **kwargs,
    ):

        super().__init__(**kwargs)
        self._json = {}
        self._databricks_token = databricks_token
        self._databricks_host = databricks_host
        self._timeout_seconds = timeout_seconds
        self._databricks_retry_limit = databricks_retry_limit
        self._databricks_retry_delay = databricks_retry_delay
        self._polling_period = polling_period
        self._polling_timeout = polling_timeout
        self._end_point = f"https://{databricks_host}/api/{DATABRICKS_API_VERSION}"

        if spark_jar_task is not None:
            self._json["spark_jar_task"] = spark_jar_task
        if notebook_task is not None:
            self._json["notebook_task"] = notebook_task
        if spark_python_task is not None:
            self._json["spark_python_task"] = spark_python_task
        if spark_submit_task is not None:
            self._json["spark_submit_task"] = spark_submit_task
        if new_cluster is not None:
            self._json["new_cluster"] = new_cluster
        if libraries is not None:
            self._json["libraries"] = libraries
        if timeout_seconds is not None:
            self._json["timeout_seconds"] = timeout_seconds
        if self.name is not None:
            self._json["run_name"] = self.name
        if existing_cluster_id is not None:
            self._json["existing_cluster_id"] = existing_cluster_id
            self.logger.info(f"Using cluster ID: {self._json['existing_cluster_id']}")
        else:
            if existing_cluster_name is not None:
                self._json["existing_cluster_id"] = self._get_cluster_id(
                    existing_cluster_name
                )
                self.logger.info(
                    f"Using cluster ID: {self._json['existing_cluster_id']}"
                )

    @property
    def databricks_host(self):
        return self._databricks_host

    @property
    def timeout_seconds(self):
        return self._timeout_seconds

    @property
    def databricks_retry_limit(self):
        return self._databricks_retry_limit

    @property
    def databricks_retry_delay(self):
        return self._databricks_retry_delay

    @property
    def polling_period(self):
        return self._polling_period

    @property
    def polling_timeout(self):
        return self._polling_timeout

    @property
    def json(self):
        return self._json

    def _get_cluster_id(self, cluster_name):
        """
        Utility function to get a cluster id from cluster name
        Args:
            - name: cluster name

        Returns:
            - The cluster id
        """
        self.logger.info("Fetching existing clusters information ...")
        query = f"{self._end_point}/clusters/list"
        response = requests.get(
            url=query,
            timeout=self._timeout_seconds,
            headers={
                "Authorization": f"Bearer {self._databricks_token}",
                "User-Agent": USER_AGENT,
            },
        )
        response.raise_for_status()
        data = response.json()
        clusters = dict(
            map(
                lambda k: (k["default_tags"]["ClusterName"], k["cluster_id"]),
                data["clusters"],
            )
        )

        if cluster_name not in clusters:
            raise Exception(f"Cluster {cluster_name} does not exist !")
        return clusters[cluster_name]

    def _wait_for_run_to_complete(self, run_id, polling_period, timeout=3600):
        """
        Fetch Databricks run status via api/../jobs/run/get?run_id=<RUN_ID> until run state
        is terminated. A run is terminated when matching either SUCCESS, FAILED, TIMEDOUT or CANCELED

        Args:
            - run_id: Databricks run Id
            - polling_period: Delay in seconds between each API call
            - timeout: Timeout

        Returns:
            - Run response payload as python dict,
              see https://docs.databricks.com/dev-tools/api/latest/jobs.html#runs-get
        """
        query = f"{self._end_point}/jobs/runs/get?run_id={run_id}"
        start_time = time()
        while time() - start_time < timeout:
            response = requests.get(
                url=query,
                timeout=self._timeout_seconds,
                headers={
                    "Authorization": f"Bearer {self._databricks_token}",
                    "User-Agent": USER_AGENT,
                },
            )

            response.raise_for_status()
            data = response.json()
            run_page, run_name, lifecycle_state = (
                data["run_page_url"],
                data["run_name"],
                data["state"]["life_cycle_state"],
            )

            if "result_state" in data["state"]:
                status = data["state"]["result_state"]
                self.logger.info(
                    f"Databricks {run_name} is {status}... For more info please visit {run_page}"
                )
                return data

            self.logger.debug(
                f"Databricks {run_name} is {lifecycle_state}... For more info please visit {run_page}"
            )
            sleep(polling_period)

        raise Exception(
            f"DatabricksRunSubmit timeout ! Unable to fetch {query} in the time imparted"
        )

    def run(self):
        """
        Task run method.

        Returns:
            - Run response payload as python dict,
              see https://docs.databricks.com/dev-tools/api/latest/jobs.html#runs-get
        """
        attempt_num = 1
        while attempt_num < self._databricks_retry_limit:
            self.logger.info(f"{self.name}: try # {attempt_num} ")
            try:
                response = requests.post(
                    url=f"{self._end_point}/jobs/runs/submit",
                    json=self._json,
                    headers={
                        "Authorization": f"Bearer {self._databricks_token}",
                        "User-Agent": USER_AGENT,
                    },
                    timeout=self._timeout_seconds,
                )

                response.raise_for_status()
                json_data = response.json()
                if "run_id" not in json_data:
                    raise requests.exceptions.RequestException

                result_data = self._wait_for_run_to_complete(
                    run_id=json_data["run_id"],
                    polling_period=self._polling_period,
                    timeout=self._polling_timeout,
                )

                result_status, run_name, run_page = (
                    result_data["state"]["result_state"],
                    result_data["run_name"],
                    result_data["run_page_url"],
                )

                if result_status != "SUCCESS":
                    raise Exception(
                        f"Task {run_name} failed with status {result_status}... "
                        f"For more info please visit {run_page}"
                    )
                return result_data

            except requests.exceptions.RequestException as error:
                self.logger.error(error)
                attempt_num += 1
                sleep(self._databricks_retry_delay)

        raise Exception(
            f"API requests to Databricks failed {self._databricks_retry_limit} times. Giving up"
        )
