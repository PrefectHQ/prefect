from time import sleep
from typing import List

import requests


# dbt Cloud Trigger Job API -> https://docs.getdbt.com/dbt-cloud/api-v2#operation/triggerRun
__DBT_CLOUD_TRIGGER_JOB_API_ENDPOINT_V2 = (
    "https://cloud.getdbt.com/api/v2/accounts/{accountId}/jobs/{jobId}/run/"
)

# dbt Cloud Get Run API -> https://docs.getdbt.com/dbt-cloud/api-v2#operation/getRunById
__DBT_CLOUD_GET_RUN_API_ENDPOINT_V2 = (
    "https://cloud.getdbt.com/api/v2/accounts/{accountId}/runs/{runId}/"
)

# dbt Cloud Get Run Artifacts API ->
#   https://docs.getdbt.com/dbt-cloud/api-v2#operation/getArtifactsByRunId
__DBT_CLOUD_GET_RUN_ARTIFACT_ENDPOINT_V2 = (
    "https://cloud.getdbt.com/api/v2/accounts/{accountId}/runs/{runId}/artifacts/{path}"
)

dbt_cloud_artifact_paths = ("manifest.json", "run_results.json", "catalog.json")


class DbtCloudBaseException(Exception):
    """"""

    pass


class TriggerDbtCloudRunFailed(DbtCloudBaseException):
    """Raised when triggering a dbt job run fails"""

    pass


class GetDbtCloudRunFailed(DbtCloudBaseException):
    """Raised when details for a dbt Cloud job run cannot be retrieved"""

    pass


class DbtCloudRunFailed(DbtCloudBaseException):
    """Raised when a dbt Cloud run fails"""

    pass


class DbtCloudRunCanceled(DbtCloudBaseException):
    """Raised when a dbt Cloud run has been canceled before completion"""

    pass


class DbtCloudRunTimedOut(DbtCloudBaseException):
    """Raised when a dbt Cloud run does not complete in the provided time"""

    pass


def trigger_job_run(
    account_id: int, job_id: int, token: str, cause: str, additional_args: dict
) -> dict:
    """
    Trigger a dbt Cloud job run

    Args:
        - account_id (int): dbt Cloud account ID
        - job_id (int): dbt Cloud job ID
        - token (str): dbt Cloud token
        - cause (str): the reason describing why the job run is being triggered
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
        raise TriggerDbtCloudRunFailed(trigger_request.reason)

    return trigger_request.json()["data"]


def wait_for_job_run(
    account_id: int, token: str, run_id: int, max_wait_time: int = None
) -> dict:
    """
    Get a dbt Cloud job run.
    Please note that this function will fail if any call to dbt Cloud APIs fail.

    Args:
        - account_id (int): dbt Cloud account ID
        - token (str): dbt Cloud token
        - run_id (int): dbt Cloud job run ID
        - max_wait_time: the number od seconds to wait for the job to complete

    Returns:
        - The job run result, namely the "data" key in the API response

    Raises:
        - prefect.engine.signals.FAIL: if "finished_at" is not None and the result status != 10
    """
    wait_time_between_api_calls = 10
    elapsed_wait_time = 0
    while not max_wait_time or elapsed_wait_time <= max_wait_time:
        get_run_request = requests.get(
            url=__DBT_CLOUD_GET_RUN_API_ENDPOINT_V2.format(
                accountId=account_id, runId=run_id
            ),
            headers={"Authorization": f"Bearer {token}"},
        )

        if get_run_request.status_code != 200:
            raise GetDbtCloudRunFailed(get_run_request.reason)

        result = get_run_request.json()["data"]
        if result["finished_at"]:
            if result["status"] == 10:
                return result
            elif result["status"] == 20:
                raise DbtCloudRunFailed(f"Job run with ID: {run_id} failed.")
            elif result["status"] == 30:
                raise DbtCloudRunCanceled(f"Job run with ID: {run_id} cancelled.")
        sleep(wait_time_between_api_calls)
        elapsed_wait_time += wait_time_between_api_calls

    raise DbtCloudRunTimedOut(
        f"Max attempts reached while checking status of job run with ID: {run_id}"
    )


def create_run_artifact_links(account_id: int, run_id: int) -> List[str]:
    """
    Generates a URL that can be used to download an artifact from a dbt run

    Args:
        - account_id (int): dbt Cloud account ID
        - run_id (int): dbt Cloud job run ID

    Returns:
        - List of artifact download URLs

    """
    return [
        __DBT_CLOUD_GET_RUN_ARTIFACT_ENDPOINT_V2.format(
            accountId=account_id, runId=run_id, path=artifact_path
        )
        for artifact_path in dbt_cloud_artifact_paths
    ]
