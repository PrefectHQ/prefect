"""Tasks for interacting with AWS Batch"""

from typing import Any, Dict, Optional

from prefect import get_run_logger, task
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect_aws.credentials import AwsCredentials


@task
async def batch_submit(
    job_name: str,
    job_queue: str,
    job_definition: str,
    aws_credentials: AwsCredentials,
    **batch_kwargs: Optional[Dict[str, Any]],
) -> str:
    """
    Submit a job to the AWS Batch job service.

    Args:
        job_name: The AWS batch job name.
        job_queue: Name of the AWS batch job queue.
        job_definition: The AWS batch job definition.
        aws_credentials: Credentials to use for authentication with AWS.
        **batch_kwargs: Additional keyword arguments to pass to the boto3
            `submit_job` function. See the documentation for
            [submit_job](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/batch.html#Batch.Client.submit_job)
            for more details.

    Returns:
        The id corresponding to the job.

    Example:
        Submits a job to batch.

        ```python
        from prefect import flow
        from prefect_aws import AwsCredentials
        from prefect_aws.batch import batch_submit


        @flow
        def example_batch_submit_flow():
            aws_credentials = AwsCredentials(
                aws_access_key_id="acccess_key_id",
                aws_secret_access_key="secret_access_key"
            )
            job_id = batch_submit(
                "job_name",
                "job_queue",
                "job_definition",
                aws_credentials
            )
            return job_id

        example_batch_submit_flow()
        ```

    """  # noqa
    logger = get_run_logger()
    logger.info("Preparing to submit %s job to %s job queue", job_name, job_queue)

    batch_client = aws_credentials.get_boto3_session().client("batch")

    response = await run_sync_in_worker_thread(
        batch_client.submit_job,
        jobName=job_name,
        jobQueue=job_queue,
        jobDefinition=job_definition,
        **batch_kwargs,
    )
    return response["jobId"]
