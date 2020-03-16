import base64
import io
import json
from typing import TYPE_CHECKING, Any, Optional

import cloudpickle

import prefect
from prefect.engine.result.base import Result
from prefect.client import Secret
from prefect.utilities import logging

if TYPE_CHECKING:
    import google.cloud


class S3Result(Result):
    """
    Result Handler for writing to and reading from an AWS S3 Bucket.

    For authentication, there are two options: you can set a Prefect Secret containing
    your AWS access keys which will be passed directly to the `boto3` client, or you can
    [configure your flow's runtime environment](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#guide-configuration)
    for `boto3`.

    Args:
        - bucket (str): the name of the bucket to write to / read from
        - credentials_secret (str, optional): the name of the Prefect Secret
            that stores your AWS credentials; this Secret must be a JSON string
            with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
            passed directly to `boto3`.  If not provided, `boto3`
            will fall back on standard AWS rules for authentication.
    """

    def __init__(self, bucket: str, credentials_secret: str = None, **kwargs) -> None:
        self.bucket = bucket
        self.credentials_secret = credentials_secret
        self.logger = logging.get_logger(type(self).__name__)
        super().__init__(**kwargs)

    def initialize_client(self) -> None:
        """
        Initializes an S3 Client.
        """
        import boto3

        aws_access_key = None
        aws_secret_access_key = None

        if self.credentials_secret:
            aws_credentials = Secret(self.credentials_secret).get()
            if isinstance(aws_credentials, str):
                aws_credentials = json.loads(aws_credentials)

            aws_access_key = aws_credentials["ACCESS_KEY"]
            aws_secret_access_key = aws_credentials["SECRET_ACCESS_KEY"]

        # use a new boto session when initializing in case we are in a new thread
        # see https://boto3.amazonaws.com/v1/documentation/api/latest/guide/resources.html?#multithreading-multiprocessing
        session = boto3.session.Session()
        s3_client = session.client(
            "s3",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_access_key,
        )
        self.client = s3_client

    @property
    def client(self) -> "boto3.client":
        """
        Initializes a client if we believe we are in a new thread.
        We consider ourselves in a new thread if we haven't stored a client yet in the current context.
        """
        if not prefect.context.get("boto3client"):
            self.initialize_client()
            prefect.context["boto3client"] = self._client
        return self._client

    @client.setter
    def client(self, val: Any) -> None:
        self._client = val

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        if "_client" in state:
            del state["_client"]
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)

    def write(self) -> str:
        """
        Writes the result value to a location in S3 and returns the resulting URI.

        Returns:
            - str: the S3 URI
        """

        uri = self.render_destination()

        self.logger.debug("Starting to upload result to {}...".format(uri))

        ## prepare data
        binary_data = base64.b64encode(cloudpickle.dumps(self.value))
        stream = io.BytesIO(binary_data)

        ## upload
        self.client.upload_fileobj(stream, Bucket=self.bucket, Key=uri)
        self.logger.debug("Finished uploading result to {}.".format(uri))

        return uri

    def read(self, loc: Optional[str] = None) -> Any:
        """
        Reads a result from a S3 bucket

        Args:
            - uri (str, optional): the S3 URI

        Returns:
            - Any: the read result
        """
        try:
            uri = loc or self.render_destination()

            self.logger.debug("Starting to download result from {}...".format(uri))
            stream = io.BytesIO()

            ## download
            self.client.download_fileobj(Bucket=self.bucket, Key=uri, Fileobj=stream)
            stream.seek(0)

            try:
                self.value = cloudpickle.loads(base64.b64decode(stream.read()))
            except EOFError:
                self.value = None
            self.logger.debug("Finished downloading result from {}.".format(uri))

        except Exception as exc:
            self.logger.exception(
                "Unexpected error while reading from S3: {}".format(repr(exc))
            )
            self.value = None

        return self.value

    def exists(self) -> bool:
        """
        Checks whether the target result exists in the S3 bucket.

        Does not validate whether the result is `valid`, only that it is present.

        Returns:
            - bool: whether or not the target result exists in the bucket
        """
        import botocore

        uri = self.render_destination()

        try:
            self.client.get_object(Bucket=self.bucket, Key=uri).load()
        except botocore.exceptions.ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                return False
            raise
        except Exception as exc:
            self.logger.exception(
                "Unexpected error while reading from S3: {}".format(repr(exc))
            )
            raise
        return True
