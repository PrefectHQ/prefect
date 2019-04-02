import base64
import io
import json
import uuid
from typing import Any, TYPE_CHECKING

import cloudpickle
import pendulum

from prefect.client import Secret
from prefect.engine.result_handlers import ResultHandler


if TYPE_CHECKING:
    import boto3


class S3ResultHandler(ResultHandler):
    """
    Result Handler for writing to and reading from an AWS S3 Bucket.

    Args:
        - bucket (str): the name of the bucket to write to / read from

    Note that for this result handler to work properly, your AWS Credentials must
    be made available in the `"AWS_CREDENTIALS"` Prefect Secret.
    """

    def __init__(self, bucket: str = None) -> None:
        self.bucket = bucket
        self.initialize_client()
        super().__init__()

    def initialize_client(self) -> None:
        """
        Initializes an S3 Client.
        """
        import boto3

        aws_credentials = Secret("AWS_CREDENTIALS").get()
        if isinstance(aws_credentials, str):
            aws_credentials = json.loads(aws_credentials)

        aws_access_key = aws_credentials["ACCESS_KEY"]
        aws_secret_access_key = aws_credentials["SECRET_ACCESS_KEY"]
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_access_key,
        )
        self.client = s3_client

    @property
    def client(self) -> "boto3.client":
        if not hasattr(self, "_client"):
            self.initialize_client()
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

    def write(self, result: Any) -> str:
        """
        Given a result, writes the result to a location in S3
        and returns the resulting URI.

        Args:
            - result (Any): the written result

        Returns:
            - str: the S3 URI
        """
        date = pendulum.now("utc").format("Y/M/D")
        uri = "{date}/{uuid}.prefect_result".format(date=date, uuid=uuid.uuid4())
        self.logger.debug("Starting to upload result to {}...".format(uri))

        ## prepare data
        binary_data = base64.b64encode(cloudpickle.dumps(result))
        stream = io.BytesIO(binary_data)

        ## upload
        self.client.upload_fileobj(stream, Bucket=self.bucket, Key=uri)
        self.logger.debug("Finished uploading result to {}.".format(uri))
        return uri

    def read(self, uri: str) -> Any:
        """
        Given a uri, reads a result from S3, reads it and returns it

        Args:
            - uri (str): the S3 URI

        Returns:
            - Any: the read result
        """
        try:
            self.logger.debug("Starting to download result from {}...".format(uri))
            stream = io.BytesIO()

            ## download
            self.client.download_fileobj(Bucket=self.bucket, Key=uri, Fileobj=stream)
            stream.seek(0)

            try:
                return_val = cloudpickle.loads(base64.b64decode(stream.read()))
            except EOFError:
                return_val = None
            self.logger.debug("Finished downloading result from {}.".format(uri))

        except Exception as exc:
            self.logger.error(exc)
            return_val = None

        return return_val
