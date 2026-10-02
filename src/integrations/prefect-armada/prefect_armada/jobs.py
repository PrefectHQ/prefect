"""Module to define tasks for interacting with Armada jobs."""

from __future__ import annotations

import uuid
from asyncio import sleep
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeAlias

import grpc
import yaml
from armada_client.armada import job_pb2, submit_pb2
from armada_client.typings import JobState
from pydantic import Field
from typing_extensions import Self

from prefect import task
from prefect._internal.compatibility.async_dispatch import async_dispatch
from prefect._internal.concurrency.api import create_call, from_sync
from prefect.blocks.abstract import JobBlock, JobRun
from prefect_armada.credentials import ArmadaCredentials
from prefect_armada.exceptions import (
    ArmadaJobDefinitionError,
    ArmadaJobFailedError,
    ArmadaJobTimeoutError,
)
from prefect_armada.logs import read_job_log_lines
from prefect_armada.utilities import (
    TERMINAL_JOB_STATES,
    UNSUCCESSFUL_JOB_STATES,
    coerce_job_request_items,
    job_state_from_value,
)

ArmadaJobRequest: TypeAlias = dict[str, Any] | submit_pb2.JobSubmitRequestItem


@task
async def submit_job(
    armada_credentials: ArmadaCredentials,
    job_request: ArmadaJobRequest | list[ArmadaJobRequest],
    queue: str,
    job_set_id: str,
) -> submit_pb2.JobSubmitResponse:
    """Task for submitting one or more jobs to an Armada queue.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        job_request: An Armada job request, or a list of job requests. Each job
            request may be a dictionary (for example one produced by
            `yaml.safe_load`) or an Armada `JobSubmitRequestItem`.
        queue: The name of the Armada queue to submit to.
        job_set_id: The name of the Armada job set to submit to.

    Returns:
        An Armada `JobSubmitResponse` object.

    Example:
        Submit a job to the `prefect` queue:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.jobs import submit_job

        @flow
        def armada_orchestrator():
            response = submit_job(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                job_request={
                    "priority": 1,
                    "namespace": "default",
                    "podSpec": {
                        "restartPolicy": "Never",
                        "containers": [
                            {
                                "name": "prefect-job",
                                "image": "docker.io/library/ubuntu:latest",
                                "args": ["sleep", "10s"],
                                "resources": {
                                    "requests": {"cpu": "120m", "memory": "510Mi"},
                                    "limits": {"cpu": "120m", "memory": "510Mi"},
                                },
                            }
                        ],
                    },
                },
                queue="prefect",
                job_set_id="my-job-set",
            )
        ```
    """
    job_request_items = coerce_job_request_items(job_request)
    async with armada_credentials.get_client() as client:
        return await client.submit_jobs(
            queue=queue,
            job_set_id=job_set_id,
            job_request_items=job_request_items,
        )


@task
async def cancel_job(
    armada_credentials: ArmadaCredentials,
    queue: str,
    job_set_id: str,
    job_id: str,
) -> submit_pb2.CancellationResult:
    """Task for cancelling an Armada job.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        queue: The name of the Armada queue the job was submitted to.
        job_set_id: The name of the Armada job set the job belongs to.
        job_id: The ID of the job to cancel.

    Returns:
        An Armada `CancellationResult` object.

    Example:
        Cancel a job:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.jobs import cancel_job

        @flow
        def armada_orchestrator():
            result = cancel_job(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                queue="prefect",
                job_set_id="my-job-set",
                job_id="01hqk8m0z6z9jz3q0k9pz9x5nb",
            )
        ```
    """
    async with armada_credentials.get_client() as client:
        return await client.cancel_jobs(
            queue=queue,
            job_set_id=job_set_id,
            job_id=job_id,
        )


@task
async def preempt_job(
    armada_credentials: ArmadaCredentials,
    queue: str,
    job_set_id: str,
    job_id: str,
) -> Any:
    """Task for preempting a running Armada job.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        queue: The name of the Armada queue the job was submitted to.
        job_set_id: The name of the Armada job set the job belongs to.
        job_id: The ID of the job to preempt.

    Returns:
        An empty response.

    Example:
        Preempt a job:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.jobs import preempt_job

        @flow
        def armada_orchestrator():
            preempt_job(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                queue="prefect",
                job_set_id="my-job-set",
                job_id="01hqk8m0z6z9jz3q0k9pz9x5nb",
            )
        ```
    """
    async with armada_credentials.get_client() as client:
        return await client.preempt_jobs(
            queue=queue,
            job_set_id=job_set_id,
            job_id=job_id,
        )


@task
async def reprioritize_job(
    armada_credentials: ArmadaCredentials,
    queue: str,
    job_set_id: str,
    new_priority: float,
    job_ids: list[str] | None = None,
) -> submit_pb2.JobReprioritizeResponse:
    """Task for changing the priority of Armada jobs.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        queue: The name of the Armada queue the jobs were submitted to.
        job_set_id: The name of the Armada job set the jobs belong to.
        new_priority: The new priority for the jobs.
        job_ids: The IDs of the jobs to reprioritize. If not provided, every job
            in the job set is reprioritized.

    Returns:
        An Armada `JobReprioritizeResponse` object.

    Example:
        Reprioritize a job:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.jobs import reprioritize_job

        @flow
        def armada_orchestrator():
            response = reprioritize_job(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                queue="prefect",
                job_set_id="my-job-set",
                new_priority=2,
                job_ids=["01hqk8m0z6z9jz3q0k9pz9x5nb"],
            )
        ```
    """
    async with armada_credentials.get_client() as client:
        return await client.reprioritize_jobs(
            new_priority=new_priority,
            job_ids=job_ids,
            job_set_id=job_set_id,
            queue=queue,
        )


@task
async def get_job_status(
    armada_credentials: ArmadaCredentials,
    job_ids: list[str],
) -> job_pb2.JobStatusResponse:
    """Task for fetching the status of Armada jobs.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        job_ids: The IDs of the jobs to fetch status for.

    Returns:
        An Armada `JobStatusResponse` object, whose `job_states` map holds a
        state for each requested job ID.

    Example:
        Fetch the status of a job:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.jobs import get_job_status

        @flow
        def armada_orchestrator():
            response = get_job_status(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                job_ids=["01hqk8m0z6z9jz3q0k9pz9x5nb"],
            )
        ```
    """
    async with armada_credentials.get_client() as client:
        return await client.get_job_status(job_ids=job_ids)


@task
async def get_job_details(
    armada_credentials: ArmadaCredentials,
    job_ids: list[str],
) -> job_pb2.JobDetailsResponse:
    """Task for fetching the details of Armada jobs.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        job_ids: The IDs of the jobs to fetch details for.

    Returns:
        An Armada `JobDetailsResponse` object.

    Example:
        Fetch the details of a job:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.jobs import get_job_details

        @flow
        def armada_orchestrator():
            response = get_job_details(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                job_ids=["01hqk8m0z6z9jz3q0k9pz9x5nb"],
            )
        ```
    """
    async with armada_credentials.get_client() as client:
        return await client.get_job_details(job_ids=job_ids)


@task
async def get_job_errors(
    armada_credentials: ArmadaCredentials,
    job_ids: list[str],
) -> job_pb2.JobErrorsResponse:
    """Task for fetching the termination reasons of Armada jobs.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        job_ids: The IDs of the jobs to fetch errors for.

    Returns:
        An Armada `JobErrorsResponse` object, whose `job_errors` map holds an
        error message for each requested job ID.

    Example:
        Fetch the errors for a job:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.jobs import get_job_errors

        @flow
        def armada_orchestrator():
            response = get_job_errors(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                job_ids=["01hqk8m0z6z9jz3q0k9pz9x5nb"],
            )
        ```
    """
    async with armada_credentials.get_client() as client:
        return await client.get_job_errors(job_ids=job_ids)


@task
async def get_job_run_details(
    armada_credentials: ArmadaCredentials,
    run_ids: list[str],
) -> job_pb2.JobRunDetailsResponse:
    """Task for fetching the details of Armada job runs.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        run_ids: The IDs of the job runs to fetch details for.

    Returns:
        An Armada `JobRunDetailsResponse` object.

    Example:
        Fetch the details of a job run:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.jobs import get_job_run_details

        @flow
        def armada_orchestrator():
            response = get_job_run_details(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                run_ids=["01hqk8m1a7pd3q9yq5xnq7t2vc"],
            )
        ```
    """
    async with armada_credentials.get_client() as client:
        return await client.get_job_run_details(run_ids=run_ids)


class ArmadaJobRun(JobRun[dict[str, Any]]):
    """A container representing a run of an Armada job."""

    def __init__(
        self,
        armada_job: ArmadaJob,
        job_id: str,
        job_set_id: str,
    ):
        self.job_logs: dict[str, str] | None = None
        self.job_id = job_id
        self.job_set_id = job_set_id

        self._completed = False
        self._armada_job = armada_job
        self._printed_log_lines = 0
        self._job_state: JobState | None = None

    @property
    def job_state(self) -> JobState | None:
        """The last observed state of the Armada job."""
        return self._job_state

    async def _get_job_state(self) -> JobState:
        """Reads the current state of the Armada job."""
        response = await get_job_status.fn(
            armada_credentials=self._armada_job.credentials,
            job_ids=[self.job_id],
        )
        if self.job_id not in response.job_states:
            return JobState.UNKNOWN
        return job_state_from_value(response.job_states[self.job_id])

    async def _capture_logs(self, print_func: Callable | None = None):
        """Captures the job's logs, printing any lines not yet printed.

        Armada serves logs as a snapshot rather than a stream, so the full log
        is re-read on each capture and only the new lines are printed.
        """
        assert self.job_logs is not None, "Expected job logs to be initialized"
        try:
            log_lines = await read_job_log_lines.fn(
                armada_credentials=self._armada_job.credentials,
                job_id=self.job_id,
                namespace=self._armada_job.namespace,
            )
        except grpc.RpcError as exc:
            # Logs are only available while the job's pod exists, so a failure
            # here should not fail the job run.
            self.logger.warning(
                f"Unable to read logs for job {self.job_id!r}: {exc}",
            )
            return

        if print_func is not None:
            for log_line in log_lines[self._printed_log_lines :]:
                print_func(log_line.line)
        self._printed_log_lines = len(log_lines)
        self.job_logs[self.job_id] = "\n".join(log_line.line for log_line in log_lines)

    async def _cleanup(self):
        """Cancels the Armada job."""
        result = await cancel_job.fn(
            armada_credentials=self._armada_job.credentials,
            queue=self._armada_job.queue,
            job_set_id=self.job_set_id,
            job_id=self.job_id,
        )
        self.logger.info(
            f"Job {self.job_id} cancelled with {list(result.cancelled_ids)!r}."
        )

    async def await_for_completion(self, print_func: Callable | None = None):
        """Async implementation: waits for the job to complete.

        If the job has `cancel_on_timeout` set to `True`, the job will be
        cancelled if it does not complete within `timeout_seconds`.

        Raises:
            ArmadaJobFailedError: If the Armada job does not succeed.
            ArmadaJobTimeoutError: If the Armada job times out.
        """
        self.job_logs = {}

        elapsed_time = 0

        while not self._completed:
            job_expired = (
                elapsed_time > self._armada_job.timeout_seconds
                if self._armada_job.timeout_seconds
                else False
            )
            if job_expired:
                if self._armada_job.cancel_on_timeout:
                    await self._cleanup()
                raise ArmadaJobTimeoutError(
                    f"Job timed out after {elapsed_time} seconds."
                )

            self._job_state = await self._get_job_state()

            if self._job_state in TERMINAL_JOB_STATES:
                await self._capture_logs(print_func)

                if self._job_state in UNSUCCESSFUL_JOB_STATES:
                    errors = await get_job_errors.fn(
                        armada_credentials=self._armada_job.credentials,
                        job_ids=[self.job_id],
                    )
                    reason = errors.job_errors.get(self.job_id) or "no reason reported"
                    raise ArmadaJobFailedError(
                        f"Job {self.job_id!r} finished in state "
                        f"{self._job_state.name} due to {reason!r}."
                    )

                self._completed = True
                self.logger.info(
                    f"Job {self.job_id!r} has completed with state "
                    f"{self._job_state.name}."
                )
                continue

            if print_func is not None and self._job_state is JobState.RUNNING:
                await self._capture_logs(print_func)

            await sleep(self._armada_job.interval_seconds)
            if self._armada_job.timeout_seconds:
                elapsed_time += self._armada_job.interval_seconds

    @async_dispatch(await_for_completion)
    def wait_for_completion(self, print_func: Callable | None = None):
        """Waits for the job to complete.

        If the job has `cancel_on_timeout` set to `True`, the job will be
        cancelled if it does not complete within `timeout_seconds`.

        Raises:
            ArmadaJobFailedError: If the Armada job does not succeed.
            ArmadaJobTimeoutError: If the Armada job times out.
        """
        return from_sync.call_soon_in_loop_thread(
            create_call(self.await_for_completion, print_func)
        ).result()

    async def afetch_result(self) -> dict[str, Any]:
        """Async implementation: fetch the results of the job.

        Returns:
            The logs from the job, keyed by job ID.

        Raises:
            ValueError: If this method is called when the job has
                a non-terminal state.
        """
        if not self._completed:
            raise ValueError(
                "The Armada Job run is not in a completed state - "
                "be sure to call `wait_for_completion` before attempting "
                "to fetch the result."
            )
        return self.job_logs or {}

    @async_dispatch(afetch_result)
    def fetch_result(self) -> dict[str, Any]:
        """Fetch the results of the job.

        Returns:
            The logs from the job, keyed by job ID.

        Raises:
            ValueError: If this method is called when the job has
                a non-terminal state.
        """
        return from_sync.call_soon_in_loop_thread(
            create_call(self.afetch_result)
        ).result()


class ArmadaJob(JobBlock):
    """A block representing an Armada job configuration.

    Example:
        Load a saved Armada job:
        ```python
        from prefect_armada.jobs import ArmadaJob

        armada_job = ArmadaJob.load("BLOCK_NAME")
        ```
    """

    job_request: dict[str, Any] = Field(
        default=...,
        title="Job Request",
        description=(
            "The Armada job request to submit. This dictionary can be produced "
            "using `yaml.safe_load`, and holds the job's pod spec under `podSpec`."
        ),
    )
    queue: str = Field(
        default="prefect",
        description="The Armada queue to submit the job to.",
    )
    job_set_id: str | None = Field(
        default=None,
        title="Job Set ID",
        description=(
            "The Armada job set to submit the job to. If not provided, a unique "
            "job set will be generated for each run of this job."
        ),
    )
    namespace: str = Field(
        default="default",
        description="The Kubernetes namespace to run the job in.",
    )
    credentials: ArmadaCredentials = Field(
        default_factory=ArmadaCredentials,
        description="The credentials to configure a client from.",
    )
    cancel_on_timeout: bool = Field(
        default=True,
        description="Whether to cancel the job if it does not complete before timing out.",
    )
    interval_seconds: int = Field(
        default=5,
        description="The number of seconds to wait between job status checks.",
    )
    timeout_seconds: int | None = Field(
        default=None,
        description="The number of seconds to wait for the job run before timing out.",
    )

    _block_type_name = "Armada Job"
    _block_type_slug = "armada-job"
    _documentation_url = "https://docs.prefect.io/integrations/prefect-armada"

    async def atrigger(self) -> ArmadaJobRun:
        """Async implementation: submit an Armada job and return an
        `ArmadaJobRun` object.
        """
        job_set_id = self.job_set_id or f"prefect-{uuid.uuid4()}"

        job_request = {**self.job_request}
        job_request.setdefault("namespace", self.namespace)

        response = await submit_job.fn(
            armada_credentials=self.credentials,
            job_request=job_request,
            queue=self.queue,
            job_set_id=job_set_id,
        )

        if len(response.job_response_items) != 1:
            raise ArmadaJobDefinitionError(
                "Expected Armada to create exactly one job, but it reported "
                f"{len(response.job_response_items)} jobs."
            )

        job_response = response.job_response_items[0]
        if job_response.error:
            raise ArmadaJobFailedError(
                f"Unable to submit job to Armada: {job_response.error}"
            )

        self.logger.info(
            f"Job {job_response.job_id!r} submitted to queue {self.queue!r} in "
            f"job set {job_set_id!r}."
        )

        return ArmadaJobRun(
            armada_job=self,
            job_id=job_response.job_id,
            job_set_id=job_set_id,
        )

    @async_dispatch(atrigger)
    def trigger(self) -> ArmadaJobRun:
        """Submit an Armada job and return an `ArmadaJobRun` object."""
        return from_sync.call_soon_in_loop_thread(create_call(self.atrigger)).result()

    @classmethod
    def from_yaml_file(cls: type[Self], manifest_path: Path | str, **kwargs) -> Self:
        """Create an `ArmadaJob` from a YAML file.

        Args:
            manifest_path: The YAML file to create the `ArmadaJob` from.

        Returns:
            An ArmadaJob object.
        """
        with open(manifest_path, "r") as yaml_stream:
            yaml_dict = yaml.safe_load(yaml_stream)

        return cls(job_request=yaml_dict, **kwargs)
