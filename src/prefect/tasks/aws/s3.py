import boto3
import io
import uuid

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class S3Download(Task):
    """
    Task for downloading data from an S3 bucket and returning it as a string.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - aws_credentials_secret (str, optional): the name of the Prefect Secret
            which stores your AWS credentials; this Secret must be a JSON string
            with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY`
        - bucket (str, optional): the name of the S3 Bucket to download from
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        aws_credentials_secret: str = "AWS_CREDENTIALS",
        bucket: str = None,
        **kwargs
    ):
        self.aws_credentials_secret = aws_credentials_secret
        self.bucket = bucket
        super().__init__(**kwargs)

    @defaults_from_attrs("aws_credentials_secret", "bucket")
    def run(
        self,
        key: str,
        aws_credentials_secret: str = "AWS_CREDENTIALS",
        bucket: str = None,
    ):
        """
        Task run method.

        Args:
            - key (str): the name of the Key within this bucket to retrieve
            - aws_credentials_secret (str, optional): the name of the Prefect Secret
                which stores your AWS credentials; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY`
            - bucket (str, optional): the name of the S3 Bucket to download from

        Returns:
            - str: the contents of this Key / Bucket, as a string
        """
        if bucket is None:
            raise ValueError("A bucket name must be provided.")

        ## get AWS credentials
        aws_credentials = Secret(aws_credentials_secret).get()
        aws_access_key = aws_credentials["ACCESS_KEY"]
        aws_secret_access_key = aws_credentials["SECRET_ACCESS_KEY"]
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_access_key,
        )

        stream = io.BytesIO()

        ## download
        s3_client.download_fileobj(Bucket=bucket, Key=key, Fileobj=stream)

        ## prepare data and return
        stream.seek(0)
        output = stream.read()
        return output.decode()


class S3Upload(Task):
    """
    Task for uploading string data (e.g., a JSON string) to an S3 bucket.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - aws_credentials_secret (str, optional): the name of the Prefect Secret
            which stores your AWS credentials; this Secret must be a JSON string
            with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY`
        - bucket (str, optional): the name of the S3 Bucket to upload to
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        aws_credentials_secret: str = "AWS_CREDENTIALS",
        bucket: str = None,
        **kwargs
    ):
        self.aws_credentials_secret = aws_credentials_secret
        self.bucket = bucket
        super().__init__(**kwargs)

    @defaults_from_attrs("aws_credentials_secret", "bucket")
    def run(
        self,
        data: str,
        key: str = None,
        aws_credentials_secret: str = "AWS_CREDENTIALS",
        bucket: str = None,
    ):
        """
        Task run method.

        Args:
            - data (str): the data payload to upload
            - key (str, optional): the Key to upload the data under; if not
                provided, a random `uuid` will be created
            - aws_credentials_secret (str, optional): the name of the Prefect Secret
                which stores your AWS credentials; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY`
            - bucket (str, optional): the name of the S3 Bucket to upload to

        Returns:
            - str: the name of the Key the data payload was uploaded to
        """
        if bucket is None:
            raise ValueError("A bucket name must be provided.")

        ## get AWS credentials
        aws_credentials = Secret(aws_credentials_secret).get()
        aws_access_key = aws_credentials["ACCESS_KEY"]
        aws_secret_access_key = aws_credentials["SECRET_ACCESS_KEY"]
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_access_key,
        )

        ## prepare data
        try:
            stream = io.BytesIO(data)
        except TypeError:
            stream = io.BytesIO(data.encode())

        ## create key if not provided
        if key is None:
            key = str(uuid.uuid4())

        ## upload
        s3_client.upload_fileobj(stream, Bucket=bucket, Key=key)
        return key
