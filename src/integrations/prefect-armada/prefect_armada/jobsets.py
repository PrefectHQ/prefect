"""Module to define tasks for interacting with Armada job sets."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from armada_client.armada import job_pb2, submit_pb2
from armada_client.typings import JobState

from prefect import task
from prefect_armada.credentials import ArmadaCredentials
from prefect_armada.utilities import job_state_from_value


@task
async def cancel_jobset(
    armada_credentials: ArmadaCredentials,
    queue: str,
    job_set_id: str,
    filter_states: Sequence[JobState | str | int] | None = None,
) -> Any:
    """Task for cancelling the jobs in an Armada job set.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        queue: The name of the Armada queue the job set was submitted to.
        job_set_id: The name of the Armada job set to cancel.
        filter_states: If provided, only jobs in these states are cancelled.
            States may be given as `JobState` members, names, or values.

    Returns:
        An empty response.

    Example:
        Cancel every queued job in a job set:
        ```python
        from armada_client.typings import JobState
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.jobsets import cancel_jobset

        @flow
        def armada_orchestrator():
            cancel_jobset(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                queue="prefect",
                job_set_id="my-job-set",
                filter_states=[JobState.QUEUED],
            )
        ```
    """
    states = [job_state_from_value(state) for state in filter_states or []]
    async with armada_credentials.get_client() as client:
        return await client.cancel_jobset(
            queue=queue,
            job_set_id=job_set_id,
            filter_states=states,
        )


@task
async def reprioritize_jobset(
    armada_credentials: ArmadaCredentials,
    queue: str,
    job_set_id: str,
    new_priority: float,
) -> submit_pb2.JobReprioritizeResponse:
    """Task for changing the priority of every job in an Armada job set.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        queue: The name of the Armada queue the job set was submitted to.
        job_set_id: The name of the Armada job set to reprioritize.
        new_priority: The new priority for the jobs in the job set.

    Returns:
        An Armada `JobReprioritizeResponse` object.

    Example:
        Reprioritize a job set:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.jobsets import reprioritize_jobset

        @flow
        def armada_orchestrator():
            response = reprioritize_jobset(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                queue="prefect",
                job_set_id="my-job-set",
                new_priority=2,
            )
        ```
    """
    async with armada_credentials.get_client() as client:
        return await client.reprioritize_jobs(
            new_priority=new_priority,
            job_ids=None,
            job_set_id=job_set_id,
            queue=queue,
        )


@task
async def get_job_status_by_external_job_uri(
    armada_credentials: ArmadaCredentials,
    queue: str,
    job_set_id: str,
    external_job_uri: str,
) -> job_pb2.JobDetailsResponse:
    """Task for looking up jobs by their `externalJobUri` annotation.

    Prefect's Armada worker sets the `armadaproject.io/externalJobUri` annotation
    to `prefect://flow-run/<flow run id>`, so this task can find the Armada job
    for a flow run without knowing its job ID.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        queue: The name of the Armada queue the job was submitted to.
        job_set_id: The name of the Armada job set the job belongs to.
        external_job_uri: The value of the job's `externalJobUri` annotation.

    Returns:
        An Armada `JobDetailsResponse` object.

    Example:
        Look up the Armada job for a flow run:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.jobsets import get_job_status_by_external_job_uri

        @flow
        def armada_orchestrator():
            response = get_job_status_by_external_job_uri(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                queue="prefect",
                job_set_id="my-job-set",
                external_job_uri="prefect://flow-run/8b1e0f38-8a9c-4a2f-9c69-a9d2c6a7a8f1",
            )
        ```
    """
    async with armada_credentials.get_client() as client:
        return await client.get_job_status_by_external_job_uri(
            queue=queue,
            job_set_id=job_set_id,
            external_job_uri=external_job_uri,
        )


def job_states_from_values(
    values: Sequence[JobState | str | int],
) -> list[JobState]:
    """Coerces a sequence of job state representations into `JobState` members.

    Args:
        values: Job states given as `JobState` members, names, or values.

    Returns:
        A list of `JobState` members.
    """
    return [job_state_from_value(value) for value in values]
