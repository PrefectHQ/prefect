from prefect.engine.signals import FAIL
import requests
from time import sleep

# dbt Cloud Trigger Job API -> https://docs.getdbt.com/dbt-cloud/api-v2#operation/triggerRun
__DBT_CLOUD_TRIGGER_JOB_API_ENDPOINT_V2 = (
    "https://cloud.getdbt.com/api/v2/accounts/{accountId}/jobs/{jobId}/run/"
)

# dbt Cloud Get Run API -> https://docs.getdbt.com/dbt-cloud/api-v2#operation/getRunById
__DBT_CLOUD_GET_RUN_API_ENDPOINT_V2 = (
    "https://cloud.getdbt.com/api/v2/accounts/{accountId}/runs/{runId}/"
)


def trigger_job_run(
    account_id: int, job_id: int, token: str, cause: str, additional_args: dict
) -> dict:
    """
    Trigger a dbt Cloud job run

    Args:
        - account_id (int): dbt Cloud account ID
        - job_id (int): dbt Cloud job ID
        - token (string): dbt Cloud token
        - cause (string): the reason describing why the job run is being triggered
        - additional_args (dict): additional information to pass to the Trigger Job Run API

    Returns:
        - The trigger run result, namely the "data" key in the API response

    Raises:
        - prefect.engine.signals.FAIL: when the response code is != 200
    """
    data = additional_args if additional_args else {}
    data["cause"] = cause
    trigger_request = requests.post(
        url=__DBT_CLOUD_TRIGGER_JOB_API_ENDPOINT_V2.format(
            accountId=account_id, jobId=job_id
        ),
        headers={"Authorization": f"Bearer {token}"},
        data=data,
    )

    if trigger_request.status_code != 200:
        raise FAIL(message=trigger_request.reason)

    return trigger_request.json()["data"]


def get_job_run(
    account_id: int, token: str, run_id: int, max_attempts: int, wait_interval: int
) -> dict:
    """
    Get a dbt Cloud job run

    Args:
        - account_id (int): dbt Cloud account ID
        - token (string): dbt Cloud token
        - run_id (int): dbt Cloud job run ID
        - max_attempts: the maximum number of calls to make to the Get Job Run API
        - wait_interval: the number of seconds to wait between API calls

    Returns:
        - The job run result, namely the "data" key in the API response

    Raises:
        - prefect.engine.signals.FAIL: if "finished_at" is not None and the result status != 10
    """
    attempts = 1
    while not max_attempts or attempts <= max_attempts:
        get_run_request = requests.get(
            url=__DBT_CLOUD_GET_RUN_API_ENDPOINT_V2.format(
                accountId=account_id, runId=run_id
            ),
            headers={"Authorization": f"Bearer {token}"},
        )

        if get_run_request.status_code != 200:
            raise FAIL(message=get_run_request.reason)

        result = get_run_request.json()["data"]
        if result["finished_at"]:
            if result["status"] == 10:
                return result
            elif result["status"] == 20:
                raise FAIL(message=f"Job run with ID: {run_id} failed.")
            elif result["status"] == 30:
                raise FAIL(message=f"Job run with ID: {run_id} cancelled.")
        sleep(wait_interval)
        attempts += 1

    raise FAIL(
        message=f"Max attempts reached while checking status of job run with ID: {run_id}"
    )
