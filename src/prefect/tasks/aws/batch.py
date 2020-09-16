import time
import typing
import random

import botocore

from prefect import Task
from prefect.engine.signals import FAIL
from prefect.utilities.aws import get_boto_client
from prefect.utilities.tasks import defaults_from_attrs


BATCH_JOB_STATES = {
    "SUBMITTED": 0,
    "PENDING": 1,
    "RUNNABLE": 2,
    "STARTING": 3,
    "RUNNING": 4,
    "SUCCEEDED": 5,
    "FAILED": 5,
}


class BatchSubmit(Task):
    """
    Task for submitting a job to AWS batch.

    For authentication, there are two options: you can set the `AWS_CREDENTIALS` Prefect Secret
    containing your AWS access keys which will be passed directly to the `boto3` client, or you
    can [configure your flow's runtime
    environment](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#guide-configuration)
    for `boto3`.

    Args:
        - job_name (str, optional): The AWS batch job name.
        - job_definition (str, optional): The AWS batch job definition.
        - job_queue (str, optional): Name of the AWS batch job queue.
        - boto_kwargs (dict, optional): additional kekyword arguments to forward to the boto client.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        job_name: str = None,
        job_definition: str = None,
        job_queue: str = None,
        boto_kwargs: dict = None,
        **kwargs,
    ):
        self.job_name = job_name
        self.job_definition = job_definition
        self.job_queue = job_queue

        if boto_kwargs is None:
            self.boto_kwargs = {}
        else:
            self.boto_kwargs = boto_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs("job_name", "job_definition", "job_queue")
    def run(
        self,
        job_name: str,
        job_definition: str,
        job_queue: str,
        batch_kwargs: dict = None,
        job_exit_state: str = "SUBMITTED",
        max_wait_time: int = 86400,
        backoff_callback: typing.Callable = None,
        state_retries: int = 10,
        on_exit: typing.Callable = None,
        on_failure: typing.Callable = None,
        credentials: str = None,
    ):
        """
        Submit a job to the AWS Batch job service.

        Args:
            - job_name (str, optional): The AWS batch job name.
            - job_definition (str, optional): The AWS batch job definition.
            - job_queue (str, optional): Name of the AWS batch job queue.
            - batch_kwargs (dict, optional): Additional keyword arguments to pass to the boto3
                `submit_job` function. See the [submit_job](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/batch.html#Batch.Client.submit_job)
                documentation for more details.
            - job_exit_state (str, optional): One of 'SUBMITTED', 'PENDING', 'RUNNABLE', 'STARTING',
                'RUNNING', SUCCEEDED', or 'FAILED'. Specify what job state to wait for before
                returning to the caller. Defaults to 'SUBMITTED' (return immediately upon successful
                job submission). Note that because we poll irregularly for the job state, there is no
                guarantee that the method returns with the specified state, only that it returns with
                the specified state OR a later state. E.g., if the `job_exit_state` is 'STARTING',
                the task may return with 'RUNNING', but never 'PENDING'.
            - max_wait_time (int, optional): The maximum amount of time we wait for the `job_exit_state`
                before throwing an error.
            - backoff_callback (Callable, optional): Callback that determines how frequently we poll the
                batch API endpoint for the job state. Takes an integer representing which number retry
                we are on, and returns an integer representing the number of seconds to wait before
                polling for the job state again. Defaults to using quadratic backoff with a max wait
                time of 15 minutes between job state requests.
            - state_retries (int, optional): Specifies the number of times to retry fetching the job
                state.
            - job_state_callbacks (dict, optional): A dictionary mapping job_exit_state strings to
                callback functions.
            - credentials (dict, optional): your AWS credentials passed from an upstream
                Secret task; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
                passed directly to `boto3`.  If not provided here or in context, `boto3`
                will fall back on standard AWS rules for authentication.
        """
        if job_exit_state not in BATCH_JOB_STATES.keys():
            raise ValueError(f"Unrecognized batch job state '{job_exit_state}'")

        batch_client = get_boto_client(
            "batch", credentials=credentials, **self.boto_kwargs
        )
        try:
            response = batch_client.submit_job(
                jobName=job_name,
                jobQueue=job_queue,
                jobDefinition=job_definition,
                **batch_kwargs
            )

            if not response.get("jobId"):
                raise FAIL("AWS Batch submit response contains no job ID.")

            job_id = response["jobId"]
            state = "SUBMITTED"

            if job_exit_state != "SUBMITTED":
                state = self._wait(
                    batch_client,
                    job_id,
                    job_exit_state,
                    max_wait_time,
                    backoff_callback,
                    state_retries,
                )

            # Run callbacks for job failure or successful exit
            if on_failure and state == "FAILED":
                on_failure(job_id)

            if on_exit and state != "FAILED":
                on_exit(job_id)

            return {"job_id": job_id, "state": state}
        except Exception:
            raise FAIL("Failed to submit job '{job_name}' to AWS Batch.")

    def _wait(
        self,
        batch_client,
        job_id: str,
        job_exit_state: str,
        max_wait_time: int,
        backoff_callback: typing.Callable,
        state_retries: int,
    ):
        """
        Wait on AWS Batch job until it reaches a terminal state.
        """
        if not backoff_callback:
            backoff_callback = lambda x: min((random.uniform(0.5, 1) * (x + 1)**2), 900)

        total_time, num_tries = 0, 0
        while total_time < max_wait_time:
            pause = backoff_callback(num_tries)
            self.logger.info(
                f"Polling AWS Batch job {job_id} for state {job_exit_state} (expended {total_time} / {max_wait_time} seconds)"
            )
            time.sleep(pause)

            job_state = self._get_job_state(batch_client, job_id, state_retries)

            # Always exit if the job has reached a terminal state
            if job_state in {"SUCCEEDED", "FAILED"}:
                return job_state

            # If the user has specified some other terminal state that we've reached, exit there
            if (
                job_exit_state
                and BATCH_JOB_STATES[job_state] >= BATCH_JOB_STATES[job_exit_state]
            ):
                return job_state

            total_time += pause
            num_tries += 1

        raise FAIL(
            "AWS Batch job {job_id} failed to reach a terminal state after {max_wait_time} seconds."
        )

    def _get_job_state(self, batch_client, job_id: str, state_retries: int):
        """
        Get job description. Retry with delay if we get a TooManyRequestsException.
        """
        tries = 0
        while tries < state_retries:
            tries += 1
            try:
                job_response = batch_client.describe_jobs(jobs=[job_id])
                if job_response and job_response.get("jobs"):
                    return job_response["jobs"][0]["status"]
                else:
                    self.logger.error(
                        f"Job description empty for job ID {job_id}: {job_response}"
                    )

            except botocore.exceptions.ClientError as err:
                response = err.response
                self.logger.error(
                    f"Unable to fetch job description for job ID {job_id}: {response}"
                )
                if tries < state_retries:
                    error = response.get("Error", {})

                    # If the issue is throttling, wait some random amount of time and continue
                    if error.get("Code") == "TooManyRequestsException":
                        self.logger.info(
                            f"AWS Batch job {job_id} retry attempt {tries} / {state_retries}"
                        )
                        time.sleep(random.randint(5, 10))
                        continue

        raise FAIL(f"Failed to get job description for job ID {job_id}")
