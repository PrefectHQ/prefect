"""
Integrations with the AWS Glue Job.

"""

import time
from typing import Any, Optional

from pydantic import VERSION as PYDANTIC_VERSION

from prefect.blocks.abstract import JobBlock, JobRun

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import BaseModel, Field
else:
    from pydantic import BaseModel, Field

from prefect_aws import AwsCredentials

_GlueJobClient = Any


class GlueJobRun(JobRun, BaseModel):
    """Execute a Glue Job"""

    job_name: str = Field(
        ...,
        title="AWS Glue Job Name",
        description="The name of the job definition to use.",
    )

    job_id: str = Field(
        ...,
        title="AWS Glue Job ID",
        description="The ID of the job run.",
    )

    job_watch_poll_interval: float = Field(
        default=60.0,
        description=(
            "The amount of time to wait between AWS API calls while monitoring the "
            "state of an Glue Job."
        ),
    )

    _error_states = ["FAILED", "STOPPED", "ERROR", "TIMEOUT"]

    aws_credentials: AwsCredentials = Field(
        title="AWS Credentials",
        default_factory=AwsCredentials,
        description="The AWS credentials to use to connect to Glue.",
    )

    client: _GlueJobClient = Field(default=None, description="")

    async def fetch_result(self) -> str:
        """fetch glue job state"""
        job = self._get_job_run()
        return job["JobRun"]["JobRunState"]

    def wait_for_completion(self) -> None:
        """
        Wait for the job run to complete and get exit code
        """
        self.logger.info(f"watching job {self.job_name} with run id {self.job_id}")
        while True:
            job = self._get_job_run()
            job_state = job["JobRun"]["JobRunState"]
            if job_state in self._error_states:
                # Generate a dynamic exception type from the AWS name
                self.logger.error(f"job failed: {job['JobRun']['ErrorMessage']}")
                raise RuntimeError(job["JobRun"]["ErrorMessage"])
            elif job_state == "SUCCEEDED":
                self.logger.info(f"job succeeded: {self.job_id}")
                break

            time.sleep(self.job_watch_poll_interval)

    def _get_job_run(self):
        """get glue job"""
        return self.client.get_job_run(JobName=self.job_name, RunId=self.job_id)


class GlueJobBlock(JobBlock):
    """Execute a job to the AWS Glue Job service.

    Attributes:
        job_name: The name of the job definition to use.
        arguments: The job arguments associated with this run.
            For this job run, they replace the default arguments set in the job
            definition itself.
            You can specify arguments here that your own job-execution script consumes,
            as well as arguments that Glue itself consumes.
            Job arguments may be logged. Do not pass plaintext secrets as arguments.
            Retrieve secrets from a Glue Connection, Secrets Manager or other secret
            management mechanism if you intend to keep them within the Job.
            [doc](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-glue-arguments.html)
        job_watch_poll_interval: The amount of time to wait between AWS API
            calls while monitoring the state of a Glue Job.
            default is 60s because of jobs that use AWS Glue versions 2.0 and later
            have a 1-minute minimum.
            [AWS Glue Pricing](https://aws.amazon.com/glue/pricing/?nc1=h_ls)

    Example:
        Start a job to AWS Glue Job.
        ```python
        from prefect import flow
        from prefect_aws import AwsCredentials
        from prefect_aws.glue_job import GlueJobBlock


        @flow
        def example_run_glue_job():
            aws_credentials = AwsCredentials(
                aws_access_key_id="your_access_key_id",
                aws_secret_access_key="your_secret_access_key"
            )
            glue_job_run = GlueJobBlock(
                job_name="your_glue_job_name",
                arguments={"--YOUR_EXTRA_ARGUMENT": "YOUR_EXTRA_ARGUMENT_VALUE"},
            ).trigger()

            return glue_job_run.wait_for_completion()


        example_run_glue_job()
        ```
    """

    job_name: str = Field(
        ...,
        title="AWS Glue Job Name",
        description="The name of the job definition to use.",
    )

    arguments: Optional[dict] = Field(
        default=None,
        title="AWS Glue Job Arguments",
        description="The job arguments associated with this run.",
    )
    job_watch_poll_interval: float = Field(
        default=60.0,
        description=(
            "The amount of time to wait between AWS API calls while monitoring the "
            "state of an Glue Job."
        ),
    )

    aws_credentials: AwsCredentials = Field(
        title="AWS Credentials",
        default_factory=AwsCredentials,
        description="The AWS credentials to use to connect to Glue.",
    )

    async def trigger(self) -> GlueJobRun:
        """trigger for GlueJobRun"""
        client = self._get_client()
        job_run_id = self._start_job(client)
        return GlueJobRun(
            job_name=self.job_name,
            job_id=job_run_id,
            job_watch_poll_interval=self.job_watch_poll_interval,
        )

    def _start_job(self, client: _GlueJobClient) -> str:
        """
        Start the AWS Glue Job
        [doc](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/glue/client/start_job_run.html)
        """
        self.logger.info(
            f"starting job {self.job_name} with arguments {self.arguments}"
        )
        try:
            response = client.start_job_run(
                JobName=self.job_name,
                Arguments=self.arguments,
            )
            job_run_id = str(response["JobRunId"])
            self.logger.info(f"job started with job run id: {job_run_id}")
            return job_run_id
        except Exception as e:
            self.logger.error(f"failed to start job: {e}")
            raise RuntimeError

    def _get_client(self) -> _GlueJobClient:
        """
        Retrieve a Glue Job Client
        """
        boto_session = self.aws_credentials.get_boto3_session()
        return boto_session.client("glue")
