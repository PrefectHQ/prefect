"""A module to define flows interacting with Armada resources."""

import asyncio
from collections.abc import Callable
from typing import Any

from prefect import flow, task
from prefect_armada.jobs import ArmadaJob


@flow
def run_armada_job(
    armada_job: ArmadaJob, print_func: Callable | None = None
) -> dict[str, Any]:
    """Flow for running an Armada job.

    Args:
        armada_job: The `ArmadaJob` block that specifies the job to run.
        print_func: A function to print the logs from the job.

    Returns:
        A dict of logs from the job, for example `{'job_id': 'job_log_str'}`.

    Raises:
        ArmadaJobFailedError: If the submitted Armada job does not succeed.

    Example:

        ```python
        from prefect_armada import ArmadaJob, run_armada_job
        from prefect_armada.credentials import ArmadaCredentials

        run_armada_job(
            armada_job=ArmadaJob.from_yaml_file(
                credentials=ArmadaCredentials.load("armada-creds"),
                manifest_path="path/to/job.yaml",
            )
        )
        ```
    """
    armada_job_run = task(armada_job.trigger)()

    task(armada_job_run.wait_for_completion)(print_func)

    return task(armada_job_run.fetch_result)()


@flow
async def run_armada_job_async(
    armada_job: ArmadaJob, print_func: Callable | None = None
) -> dict[str, Any]:
    """Flow for running an Armada job.

    Args:
        armada_job: The `ArmadaJob` block that specifies the job to run.
        print_func: A function to print the logs from the job.

    Returns:
        A dict of logs from the job, for example `{'job_id': 'job_log_str'}`.

    Raises:
        ArmadaJobFailedError: If the submitted Armada job does not succeed.

    Example:

        ```python
        from prefect_armada import ArmadaJob
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.flows import run_armada_job_async

        await run_armada_job_async(
            armada_job=ArmadaJob.from_yaml_file(
                credentials=ArmadaCredentials.load("armada-creds"),
                manifest_path="path/to/job.yaml",
            )
        )
        ```
    """
    armada_job_run = (
        await maybe_coro
        if asyncio.iscoroutine(maybe_coro := task(armada_job.trigger)())
        else maybe_coro
    )

    (
        await maybe_coro
        if asyncio.iscoroutine(
            maybe_coro := task(armada_job_run.wait_for_completion)(print_func)
        )
        else maybe_coro
    )

    return (
        await maybe_coro
        if asyncio.iscoroutine(maybe_coro := task(armada_job_run.fetch_result)())
        else maybe_coro
    )
