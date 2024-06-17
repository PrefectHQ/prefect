"""Module containing tasks and flows for interacting with dbt Cloud job runs"""

import asyncio
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from httpx import HTTPStatusError
from typing_extensions import Literal

from prefect import flow, task
from prefect.logging import get_run_logger
from prefect_dbt.cloud.credentials import DbtCloudCredentials
from prefect_dbt.cloud.exceptions import (
    DbtCloudGetRunArtifactFailed,
    DbtCloudGetRunFailed,
    DbtCloudJobRunTimedOut,
    DbtCloudListRunArtifactsFailed,
)
from prefect_dbt.cloud.utils import extract_user_message


class DbtCloudJobRunStatus(Enum):
    """dbt Cloud Job statuses."""

    QUEUED = 1
    STARTING = 2
    RUNNING = 3
    SUCCESS = 10
    FAILED = 20
    CANCELLED = 30

    @classmethod
    def is_terminal_status_code(cls, status_code: Any) -> bool:
        """
        Returns True if a status code is terminal for a job run.
        Returns False otherwise.
        """
        return status_code in [cls.SUCCESS.value, cls.FAILED.value, cls.CANCELLED.value]


@task(
    name="Get dbt Cloud job run details",
    description="Retrieves details of a dbt Cloud job run "
    "for the run with the given run_id.",
    retries=3,
    retry_delay_seconds=10,
)
async def get_dbt_cloud_run_info(
    dbt_cloud_credentials: DbtCloudCredentials,
    run_id: int,
    include_related: Optional[
        List[Literal["trigger", "job", "debug_logs", "run_steps"]]
    ] = None,
) -> Dict:
    """
    A task to retrieve information about a dbt Cloud job run.

    Args:
        dbt_cloud_credentials: Credentials for authenticating with dbt Cloud.
        run_id: The ID of the job to trigger.
        include_related: List of related fields to pull with the run.
            Valid values are "trigger", "job", "debug_logs", and "run_steps".
            If "debug_logs" is not provided in a request, then the included debug
            logs will be truncated to the last 1,000 lines of the debug log output file.

    Returns:
        The run data returned by the dbt Cloud administrative API.

    Example:
        Get status of a dbt Cloud job run:
        ```python
        from prefect import flow

        from prefect_dbt.cloud import DbtCloudCredentials
        from prefect_dbt.cloud.jobs import get_run

        @flow
        def get_run_flow():
            credentials = DbtCloudCredentials(api_key="my_api_key", account_id=123456789)

            return get_run(
                dbt_cloud_credentials=credentials,
                run_id=42
            )

        get_run_flow()
        ```
    """  # noqa
    try:
        async with dbt_cloud_credentials.get_administrative_client() as client:
            response = await client.get_run(
                run_id=run_id, include_related=include_related
            )
    except HTTPStatusError as ex:
        raise DbtCloudGetRunFailed(extract_user_message(ex)) from ex
    return response.json()["data"]


@task(
    name="List dbt Cloud job artifacts",
    description="Fetches a list of artifact files generated for a completed run.",
    retries=3,
    retry_delay_seconds=10,
)
async def list_dbt_cloud_run_artifacts(
    dbt_cloud_credentials: DbtCloudCredentials, run_id: int, step: Optional[int] = None
) -> List[str]:
    """
    A task to list the artifact files generated for a completed run.

    Args:
        dbt_cloud_credentials: Credentials for authenticating with dbt Cloud.
        run_id: The ID of the run to list run artifacts for.
        step: The index of the step in the run to query for artifacts. The
            first step in the run has the index 1. If the step parameter is
            omitted, then this method will return the artifacts compiled
            for the last step in the run.

    Returns:
        A list of paths to artifact files that can be used to retrieve the generated artifacts.

    Example:
        List artifacts of a dbt Cloud job run:
        ```python
        from prefect import flow

        from prefect_dbt.cloud import DbtCloudCredentials
        from prefect_dbt.cloud.jobs import list_dbt_cloud_run_artifacts

        @flow
        def list_artifacts_flow():
            credentials = DbtCloudCredentials(api_key="my_api_key", account_id=123456789)

            return list_dbt_cloud_run_artifacts(
                dbt_cloud_credentials=credentials,
                run_id=42
            )

        list_artifacts_flow()
        ```
    """  # noqa
    try:
        async with dbt_cloud_credentials.get_administrative_client() as client:
            response = await client.list_run_artifacts(run_id=run_id, step=step)
    except HTTPStatusError as ex:
        raise DbtCloudListRunArtifactsFailed(extract_user_message(ex)) from ex
    return response.json()["data"]


@task(
    name="Get dbt Cloud job artifact",
    description="Fetches an artifact from a completed run.",
    retries=3,
    retry_delay_seconds=10,
)
async def get_dbt_cloud_run_artifact(
    dbt_cloud_credentials: DbtCloudCredentials,
    run_id: int,
    path: str,
    step: Optional[int] = None,
) -> Union[Dict, str]:
    """
    A task to get an artifact generated for a completed run. The requested artifact
    is saved to a file in the current working directory.

    Args:
        dbt_cloud_credentials: Credentials for authenticating with dbt Cloud.
        run_id: The ID of the run to list run artifacts for.
        path: The relative path to the run artifact (e.g. manifest.json, catalog.json,
            run_results.json)
        step: The index of the step in the run to query for artifacts. The
            first step in the run has the index 1. If the step parameter is
            omitted, then this method will return the artifacts compiled
            for the last step in the run.

    Returns:
        The contents of the requested manifest. Returns a `Dict` if the
            requested artifact is a JSON file and a `str` otherwise.

    Examples:
        Get an artifact of a dbt Cloud job run:
        ```python
        from prefect import flow

        from prefect_dbt.cloud import DbtCloudCredentials
        from prefect_dbt.cloud.runs import get_dbt_cloud_run_artifact

        @flow
        def get_artifact_flow():
            credentials = DbtCloudCredentials(api_key="my_api_key", account_id=123456789)

            return get_dbt_cloud_run_artifact(
                dbt_cloud_credentials=credentials,
                run_id=42,
                path="manifest.json"
            )

        get_artifact_flow()
        ```

        Get an artifact of a dbt Cloud job run and write it to a file:
        ```python
        import json

        from prefect import flow

        from prefect_dbt.cloud import DbtCloudCredentials
        from prefect_dbt.cloud.jobs import get_dbt_cloud_run_artifact

        @flow
        def get_artifact_flow():
            credentials = DbtCloudCredentials(api_key="my_api_key", account_id=123456789)

            get_run_artifact_result = get_dbt_cloud_run_artifact(
                dbt_cloud_credentials=credentials,
                run_id=42,
                path="manifest.json"
            )

            with open("manifest.json", "w") as file:
                json.dump(get_run_artifact_result, file)

        get_artifact_flow()
        ```
    """  # noqa

    try:
        async with dbt_cloud_credentials.get_administrative_client() as client:
            response = await client.get_run_artifact(
                run_id=run_id, path=path, step=step
            )
    except HTTPStatusError as ex:
        raise DbtCloudGetRunArtifactFailed(extract_user_message(ex)) from ex

    if path.endswith(".json"):
        artifact_contents = response.json()
    else:
        artifact_contents = response.text

    return artifact_contents


@flow(
    name="Wait for dbt Cloud job run",
    description="Waits for a dbt Cloud job run to finish running.",
)
async def wait_for_dbt_cloud_job_run(
    run_id: int,
    dbt_cloud_credentials: DbtCloudCredentials,
    max_wait_seconds: int = 900,
    poll_frequency_seconds: int = 10,
) -> Tuple[DbtCloudJobRunStatus, Dict]:
    """
    Waits for the given dbt Cloud job run to finish running.

    Args:
        run_id: The ID of the run to wait for.
        dbt_cloud_credentials: Credentials for authenticating with dbt Cloud.
        max_wait_seconds: Maximum number of seconds to wait for job to complete
        poll_frequency_seconds: Number of seconds to wait in between checks for
            run completion.

    Raises:
        DbtCloudJobRunTimedOut: When the elapsed wait time exceeds `max_wait_seconds`.

    Returns:
        run_status: An enum representing the final dbt Cloud job run status
        run_data: A dictionary containing information about the run after completion.


    Example:


    """
    logger = get_run_logger()
    seconds_waited_for_run_completion = 0
    wait_for = []
    while seconds_waited_for_run_completion <= max_wait_seconds:
        run_data_future = await get_dbt_cloud_run_info(
            dbt_cloud_credentials=dbt_cloud_credentials,
            run_id=run_id,
            wait_for=wait_for,
        )
        run_data = run_data_future
        run_status_code = run_data.get("status")

        if DbtCloudJobRunStatus.is_terminal_status_code(run_status_code):
            return DbtCloudJobRunStatus(run_status_code), run_data

        wait_for = [run_data_future]
        logger.debug(
            "dbt Cloud job run with ID %i has status %s. Waiting for %i seconds.",
            run_id,
            DbtCloudJobRunStatus(run_status_code).name,
            poll_frequency_seconds,
        )
        await asyncio.sleep(poll_frequency_seconds)
        seconds_waited_for_run_completion += poll_frequency_seconds

    raise DbtCloudJobRunTimedOut(
        f"Max wait time of {max_wait_seconds} seconds exceeded while waiting "
        "for job run with ID {run_id}"
    )
