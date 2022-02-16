from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs

from prefect.tasks.databricks.databricks_hook import DatabricksHook


class DatabricksGetJobID(Task):
    """
    Finds a job_id corresponding to a job name on Databricks using the
    `api/2.1/jobs/list
    <https://docs.databricks.com/dev-tools/api/latest/jobs.html#operation/JobsList>`_
    API endpoint.

    You can use the task to feed in the job_id for DatabricksRunNow
    For example:

    ```
    conn = PrefectSecret('DATABRICKS_CONNECTION_STRING')
    job_id = DatabricksGetJobID(job_name="name", databricks_conn_secret=conn)

    notebook_run = DatabricksRunNow(
        job_id = job_id,
        notebook_params=notebook_params,
        python_params=python_params,
        spark_submit_params=spark_submit_params,
        jar_params=jar_params
    )
    notebook_run(databricks_conn_secret=conn)
    ```

    Args:
        - databricks_conn_secret (dict, optional): Dictionary representation of the Databricks
            Connection String. Structure must be a string of valid JSON. To use token based
            authentication, provide the key `token` in the string for the connection and create the
            key `host`.
            `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
            '{"host": "abcdef.xyz", "login": "ghijklmn", "password": "opqrst"}'`
            OR
            `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
            '{"host": "abcdef.xyz", "token": "ghijklmn"}'`
            See documentation of the `DatabricksSubmitRun` Task to see how to pass in the connection
            string using `PrefectSecret`.
        - job_name (str, optional): The job_name of an existing Databricks job.
        - search_limit (int, optional): Controls the number of jobs to return per API call,
            This value must be greater than 0 and less or equal to 25.
        - polling_period_seconds (int, optional): Controls the rate which we poll for the result of
            this run. By default the task will poll every 30 seconds.
        - databricks_retry_limit (int, optional): Amount of times retry if the Databricks backend is
            unreachable. Its value must be greater than or equal to 1.
        - databricks_retry_delay (float, optional): Number of seconds to wait between retries (it
            might be a floating point number).

    Returns:
        - job_id (int): Job id of the job name.
    """
    def __init__(
        self,
        databricks_conn_secret: dict,
        job_name: str,
        search_limit: int = 25,
        polling_period_seconds: int = 30,
        databricks_retry_limit: int = 3,
        databricks_retry_delay: float = 1,
        **kwargs
    ) -> None:
        self.databricks_conn_secret = databricks_conn_secret
        self.job_name = job_name
        self.search_limit = search_limit
        self.polling_period_seconds = polling_period_seconds
        self.databricks_retry_limit = databricks_retry_limit
        self.databricks_retry_delay = databricks_retry_delay

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "databricks_conn_secret",
        "job_name",
        "search_limit",
        "polling_period_seconds",
        "databricks_retry_limit",
        "databricks_retry_delay",
    )
    def run(
        self,
        databricks_conn_secret: dict = None,
        job_name: str = "",
        search_limit: int = 25,
        polling_period_seconds: int = 30,
        databricks_retry_limit: int = 3,
        databricks_retry_delay: float = 1,
    ) -> int:
        """
        Task run method.

        Args:
            - databricks_conn_secret (dict, optional): Dictionary representation of the Databricks
                Connection String. Structure must be a string of valid JSON. To use token based
                authentication, provide the key `token` in the string for the connection and create the
                key `host`.
                `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
                '{"host": "abcdef.xyz", "login": "ghijklmn", "password": "opqrst"}'`
                OR
                `PREFECT__CONTEXT__SECRETS__DATABRICKS_CONNECTION_STRING=
                '{"host": "abcdef.xyz", "token": "ghijklmn"}'`
                See documentation of the `DatabricksSubmitRun` Task to see how to pass in the connection
                string using `PrefectSecret`.
            - job_name (str, optional): The job_name of an existing Databricks job.
            - search_limit (int, optional): Controls the number of jobs to return per API call,
                This value must be greater than 0 and less or equal to 25.
            - polling_period_seconds (int, optional): Controls the rate which we poll for the result of
                this run. By default the task will poll every 30 seconds.
            - databricks_retry_limit (int, optional): Amount of times retry if the Databricks backend is
                unreachable. Its value must be greater than or equal to 1.
            - databricks_retry_delay (float, optional): Number of seconds to wait between retries (it
                might be a floating point number).

        Returns:
            - job_id (int): Job id of the job name.
        """

        self.databricks_conn_secret = databricks_conn_secret

        # Initialize Databricks Connections
        hook = self.get_hook()

        # Fetch Job ID
        self.logger.info("Searching for job_ids with name: %s ", self.job_name)
        job_id = hook.get_job_id_by_name(
            job_name=self.job_name, limit=self.search_limit
        )
        self.logger.info("%s completed successfully.", self.name)

        return job_id

    def get_hook(self):
        return DatabricksHook(
            self.databricks_conn_secret,
            retry_limit=self.databricks_retry_limit,
            retry_delay=self.databricks_retry_delay,
        )
