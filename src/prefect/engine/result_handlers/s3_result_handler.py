import base64
import io
import json
import uuid
from typing import TYPE_CHECKING, Any, Dict

import cloudpickle
import pendulum

import prefect
from prefect.client import Secret
from prefect.engine.result_handlers import ResultHandler

if TYPE_CHECKING:
    import boto3


class S3ResultHandler(ResultHandler):
    """
    Result Handler for writing to and reading from an AWS S3 Bucket.

    For authentication, there are two options: you can set a Prefect Secret containing your AWS
    access keys which will be passed directly to the `boto3` client, or you can [configure your
    flow's runtime
    environment](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#guide-configuration)
    for `boto3`.

    Args:
        - bucket (str): the name of the bucket to write to / read from
        - aws_credentials_secret (str, optional): the name of the Prefect Secret
            that stores your AWS credentials; this Secret must be a JSON string
            with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
            passed directly to `boto3`.  If not provided, `boto3`
            will fall back on standard AWS rules for authentication.
        - boto3_kwargs (dict, optional): keyword arguments to pass on to boto3 when the [client
            session](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html#boto3.session.Session.client)
            is initialized (changing the "service_name" is not permitted).
    """

    def __init__(
        self,
        bucket: str,
        aws_credentials_secret: str = None,
        boto3_kwargs: Dict[str, Any] = None,
    ) -> None:
        self.bucket = bucket
        self.aws_credentials_secret = aws_credentials_secret
        self.boto3_kwargs = boto3_kwargs or dict()
        assert (
            "service_name" not in self.boto3_kwargs.keys()
        ), 'Changing the boto3 "service_name" is not permitted!'
        self._client = None
        super().__init__()

    def initialize_client(self) -> None:
        """
        Initializes an S3 Client.
        """
        import boto3

        aws_access_key = self.boto3_kwargs.pop("aws_access_key_id", None)
        aws_secret_access_key = self.boto3_kwargs.pop("aws_secret_access_key", None)

        if self.aws_credentials_secret:
            if aws_access_key is not None or aws_secret_access_key is not None:
                self.logger.warning(
                    "'aws_access_key' or 'aws_secret_access_key' were set in 'boto3_kwargs', "
                    "ignoring those for what is populated in 'aws_credentials_secret'"
                )

            aws_credentials = Secret(self.aws_credentials_secret).get()
            if isinstance(aws_credentials, str):
                aws_credentials = json.loads(aws_credentials)

            aws_access_key = aws_credentials["ACCESS_KEY"]
            aws_secret_access_key = aws_credentials["SECRET_ACCESS_KEY"]

        # use a new boto session when initializing in case we are in a new thread see
        # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/resources.html?#multithreading-multiprocessing
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

        We consider ourselves in a new thread if we haven't stored a client yet in the current
        context.
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

    def write(self, result: Any) -> str:
        """
        Given a result, writes the result to a location in S3
        and returns the resulting URI.

        Args:
            - result (Any): the written result

        Returns:
            - str: the S3 URI
        """
        date = pendulum.now("utc").format("Y/M/D")  # type: ignore
        uri = "{date}/{uuid}.prefect_result".format(date=date, uuid=uuid.uuid4())
        self.logger.debug("Starting to upload result to {}...".format(uri))

        # prepare data
        binary_data = base64.b64encode(cloudpickle.dumps(result))
        stream = io.BytesIO(binary_data)

        # upload
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

            # download
            self.client.download_fileobj(Bucket=self.bucket, Key=uri, Fileobj=stream)
            stream.seek(0)

            try:
                return_val = cloudpickle.loads(base64.b64decode(stream.read()))
            except EOFError:
                return_val = None
            self.logger.debug("Finished downloading result from {}.".format(uri))

        except Exception as exc:
            self.logger.exception(
                "Unexpected error while reading from result handler: {}".format(
                    repr(exc)
                )
            )
            return_val = None

        return return_val
