import io
import json
from typing import Any, TYPE_CHECKING, Dict

import prefect
from prefect.client import Secret
from prefect.engine.result import Result

if TYPE_CHECKING:
    import boto3


class S3Result(Result):
    """
    Result that is written to and retrieved from an AWS S3 Bucket.

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
        - boto3_kwargs (dict, optional): keyword arguments to pass on to boto3 when the [client session](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html#boto3.session.Session.client)
            is initialized (changing the "service_name" is not permitted).
        - **kwargs (Any, optional): any additional `Result` initialization options
    """

    def __init__(
        self,
        bucket: str,
        credentials_secret: str = None,
        boto3_kwargs: Dict[str, Any] = None,
        **kwargs: Any
    ) -> None:
        self.bucket = bucket
        self.credentials_secret = credentials_secret
        self.boto3_kwargs = boto3_kwargs or dict()
        assert (
            "service_name" not in self.boto3_kwargs.keys()
        ), 'Changing the boto3 "service_name" is not permitted!'
        self._client = None
        super().__init__(**kwargs)

    def initialize_client(self) -> None:
        """
        Initializes an S3 Client.
        """
        import boto3

        aws_access_key = self.boto3_kwargs.pop("aws_access_key_id", None)
        aws_secret_access_key = self.boto3_kwargs.pop("aws_secret_access_key", None)

        if self.credentials_secret:
            if aws_access_key is not None or aws_secret_access_key is not None:
                self.logger.warning(
                    '"aws_access_key" or "aws_secret_access_key" were set in "boto3_kwargs", ignoring those for what is populated in "credentials_secret"'
                )

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
            **self.boto3_kwargs
        )
        self.client = s3_client

    @property
    def client(self) -> "boto3.client":
        """
        Initializes a client if we believe we are in a new thread.
        We consider ourselves in a new thread if we haven't stored a client yet in the current context.
        """
        if not prefect.context.get("boto3client") or not getattr(self, "_client", None):
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
        Writes the result to a location in S3 and returns the resulting URI.

        Returns:
            - str: the S3 URI
        """
        if not self._rendered_filepath:
            raise ValueError("Must call `Result.format()` first")

        self.logger.debug(
            "Starting to upload result to {}...".format(self._rendered_filepath)
        )
        binary_data = self.serialize()

        stream = io.BytesIO(binary_data)

        ## upload
        self.client.upload_fileobj(
            stream, Bucket=self.bucket, Key=self._rendered_filepath
        )
        self.logger.debug(
            "Finished uploading result to {}.".format(self._rendered_filepath)
        )

        return self._rendered_filepath

    def read(self, loc: str = None) -> Any:
        """
        Reads a result from S3, reads it and returns it

        Args:
            - loc (str, optional): the S3 URI

        Returns:
            - Any: the read result
        """
        uri = loc or self._rendered_filepath

        if not uri:
            raise ValueError("Must call `Result.format()` first")

        try:
            self.logger.debug("Starting to download result from {}...".format(uri))
            stream = io.BytesIO()

            ## download
            self.client.download_fileobj(Bucket=self.bucket, Key=uri, Fileobj=stream)
            stream.seek(0)

            try:
                self.value = self.deserialize(stream.read())
            except EOFError:
                self.value = None
            self.logger.debug("Finished downloading result from {}.".format(uri))

        except Exception as exc:
            self.logger.exception(
                "Unexpected error while reading from result handler: {}".format(
                    repr(exc)
                )
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

        if not self._rendered_filepath:
            raise ValueError("Must call `Result.format()` first")

        uri = self._rendered_filepath

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
