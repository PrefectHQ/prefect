import json
import time
import typing
import random
import importlib.resources as resources

import botocore
from botocore.exceptions import WaiterError
from botocore.waiter import WaiterModel, create_waiter_with_client

from prefect.tasks.aws import waiters
from prefect import Task
from prefect.engine.signals import FAIL
from prefect.utilities.aws import get_boto_client
from prefect.utilities.tasks import defaults_from_attrs


EXIT_CONDITION_WAITER_MAP = {
    "submitted": None,
    "exists": "JobExists",
    "running": "JobRunning",
    "complete": "JobComplete",
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
        exit_condition: str = "exists",
        waiter_delay: typing.Union[float, int] = None,
        waiter_max_attempts: int = None,
        waiter_failure_callback: typing.Callable = None,
        credentials: str = None,
    ):
        """
        Submit a job to the AWS Batch job service. Note that

        Args:
            - job_name (str, optional): The AWS batch job name.
            - job_definition (str, optional): The AWS batch job definition.
            - job_queue (str, optional): Name of the AWS batch job queue.
            - batch_kwargs (dict, optional): Additional keyword arguments to pass to the boto3
                `submit_job` function. See the [submit_job](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/batch.html#Batch.Client.submit_job)
                documentation for more details.
            - exit_condition (str, optional): Specify what job state the task should wait for before
                returning, one of 'submitted', 'exists', 'running', or 'complete'.
            - waiter_delay (float or int, optional): If waiting for an exit_condition other than
                'submitted', specify how long to wait in between polling for job status. Defaults
                to 2 seconds for 'exists', 5 seconds for 'running', and 300 seconds for 'complete'.
            - waiter_max_attempts (int, optional): If waiting for an exit condition other than
                'submitted', specify a maximum number of times to poll for job status before failing.
                Defaults to 100 attempts for 'exists' and 'running', and 288 attempts for 'complete'.
            - credentials (dict, optional): your AWS credentials passed from an upstream
                Secret task; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
                passed directly to `boto3`.  If not provided here or in context, `boto3`
                will fall back on standard AWS rules for authentication.
        """
        if exit_condition not in EXIT_CONDITION_WAITER_MAP:
            raise ValueError(f"Unrecognized exit condition '{exit_condition}'")

        batch_client = get_boto_client(
            "batch", credentials=credentials, **self.boto_kwargs
        )

        try:
            response = batch_client.submit_job(
                jobName=job_name,
                jobQueue=job_queue,
                jobDefinition=job_definition,
                **batch_kwargs,
            )

            if not response.get("jobId"):
                raise FAIL("AWS Batch submit response contains no job ID.")

            job_id = response["jobId"]

            if exit_condition == "submitted":
                return job_id

            # Instantiate waiter and wait for specified exit_condition
            with resources.open_text(waiters, "batch.json") as handle:
                waiter_model = WaiterModel(json.load(handle))

            waiter_name = EXIT_CONDITION_WAITER_MAP[exit_condition]
            waiter = create_waiter_with_client(waiter_name, waiter_model, batch_client)

            # Add custom waiter options
            if waiter_delay:
                waiter.config.delay = waiter_delay

            if waiter_max_attempts:
                waiter.config.max_attempts = waiter_max_attempts

            try:
                waiter.wait(jobs=[job_id])
            except WaiterError as e:
                raise FAIL(
                    f"Unable to wait on '{exit_condition}' for job ID '{job_id}'. Failed with: {str(e)}"
                )

            return job_id
        except Exception:
            raise FAIL("Failed to submit job '{job_name}' to AWS Batch.")
