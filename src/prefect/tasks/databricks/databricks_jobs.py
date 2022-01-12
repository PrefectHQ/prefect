from typing import Dict, List

from prefect.tasks import Task
from prefect.tasks.databricks.jobs_21_client import DatabricksJobsApiClient
from prefect.tasks.databricks.utils import deep_string_coerce
from prefect.utilities.tasks import defaults_from_attrs
from prefect.engine import signals


class Databricks21SubmitJob(Task):
    pass


class Databricks21RunNow(Task):
    def __init__(
        self,
        token: str = None,
        host: str = None,
        job_id: str = None,
        json: Dict = {},
        notebook_params: Dict = {},
        python_params: List[str] = None,
        spark_submit_params: List[str] = None,
        jar_params: List[str] = None,
        wait_for_completion: bool = True,
        max_wait_seconds: int = 300,
        polling_period_seconds: int = 30,
        **kwargs,
    ):
        self.token = token
        self.host = host
        self.job_id = job_id
        self.json = json
        self.notebook_params = notebook_params
        self.python_params = python_params
        self.spark_submit_params = spark_submit_params
        self.jar_params = jar_params
        self.wait_for_completion = wait_for_completion
        self.max_wait_seconds = max_wait_seconds
        self.polling_period_seconds = polling_period_seconds

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "token",
        "host",
        "job_id",
        "json",
        "notebook_params",
        "python_params",
        "spark_submit_params",
        "jar_params",
        "wait_for_completion",
        "max_wait_seconds",
        "polling_period_seconds",
    )
    def run(
        self,
        token: str = None,
        host: str = None,
        job_id: str = None,
        json: Dict = {},
        notebook_params: Dict = {},
        python_params: List[str] = None,
        spark_submit_params: List[str] = None,
        jar_params: List[str] = None,
        wait_for_completion: bool = True,
        max_wait_seconds: int = 300,
        polling_period_seconds: int = 30,
    ):
        if not token:
            raise ValueError("A value for token must be provided.")
        if not host:
            raise ValueError("A value for host must be provided.")

        databrick_jobs_client = DatabricksJobsApiClient(host, token)

        databricks_payloads_overrides = {
            "job_id": job_id,
            "python_params": python_params,
            "spark_submit_params": spark_submit_params,
            "jar_params": jar_params,
            "notebook_params": {
                **json.get("notebook_params", {}),
                **notebook_params,
            },
        }
        run_now_payload = deep_string_coerce(
            {
                **json,
                **{
                    key: value
                    for key, value in databricks_payloads_overrides.items()
                    if key is not None
                },
            }
        )
        self.logger.debug("Sumbitting run with config: %s", run_now_payload)
        submitted_run_id = databrick_jobs_client.run_now(run_now_payload)

        self.logger.info("Started run with run_id %s", submitted_run_id)
        run_info = databrick_jobs_client.get_run(submitted_run_id)
        self.logger.info(
            "View run status, Spark UI, and logs at %s",
            run_info.get("run_page_url", "RUN PAGE URL NOT FOUND"),
        )

        if wait_for_completion:
            self.logger.debug("Waiting for job run to complete")
            result_state = databrick_jobs_client.wait_for_run_completion(
                submitted_run_id, max_wait_seconds, polling_period_seconds
            )
            if result_state in ("FAILED", "TIMEOUT", "CANCELED"):
                raise signals.FAIL(
                    f"Job run {submitted_run_id} failed with result_state {result_state}"
                )

        return submitted_run_id
