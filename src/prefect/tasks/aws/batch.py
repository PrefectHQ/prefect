from prefect import Task
from prefect.engine.signals import FAIL
from prefect.utilities.aws import get_boto_client
from prefect.utilities.tasks import defaults_from_attrs


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
        job_name: str = None,
        job_definition: str = None,
        job_queue: str = None,
        batch_kwargs: dict = None,
        credentials: str = None,
    ):
        """
        Submit a job to the AWS Batch job service.

        Args:
            - job_name (str, optional): The AWS batch job name.
            - job_definition (str, optional): The AWS batch job definition.
            - job_queue (str, optional): Name of the AWS batch job queue.
            - batch_kwargs (dict, optional): Additional keyword arguments to pass to the boto3
                `submit_job` function. See the [submit_job](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/batch.html#Batch.Client.submit_job)  # noqa
                documentation for more details.
            - credentials (dict, optional): your AWS credentials passed from an upstream
                Secret task; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
                passed directly to `boto3`.  If not provided here or in context, `boto3`
                will fall back on standard AWS rules for authentication.
        """
        if not job_name:
            raise ValueError("A job name must be provided.")

        if not job_definition:
            raise ValueError("A job definition must be provided.")

        if not job_queue:
            raise ValueError("A job queue must be provided.")

        if not batch_kwargs:
            batch_kwargs = {}

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
        except Exception as e:
            raise FAIL(f"Failed to submit job '{job_name}' to AWS Batch.") from e

        if not response.get("jobId"):
            raise FAIL(f"AWS Batch submit response contains no job ID: {response}")

        return response["jobId"]
