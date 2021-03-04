import io
from typing import Any, TYPE_CHECKING, Dict

from prefect.engine.result import Result

if TYPE_CHECKING:
    import boto3


class S3Result(Result):
    """
    Result that is written to and retrieved from an AWS S3 Bucket.

    For authentication, there are two options: you can provide your AWS credentials to
    `prefect.context.secrets.AWS_CREDENTIALS` for automatic authentication or you can
    [configure your flow's runtime
    environment](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#guide-configuration)
    for `boto3`.

    See [Third Party Authentication](../../../orchestration/recipes/third_party_auth.html) for
    more information.

    Args:
        - bucket (str): the name of the bucket to write to / read from
        - boto3_kwargs (dict, optional): keyword arguments to pass on to boto3 when the [client
            session](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html#boto3.session.Session.client)
            is initialized.
        - **kwargs (Any, optional): any additional `Result` initialization options
    """

    def __init__(
        self, bucket: str, boto3_kwargs: Dict[str, Any] = None, **kwargs: Any
    ) -> None:
        self.bucket = bucket
        self.boto3_kwargs = boto3_kwargs or {}
        super().__init__(**kwargs)

    @property
    def client(self) -> "boto3.client":
        if getattr(self, "_client", None) is None:
            from prefect.utilities.aws import get_boto_client

            self._client = get_boto_client("s3", **self.boto3_kwargs)
        return self._client

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        state.pop("_client", None)
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)

    def write(self, value_: Any, **kwargs: Any) -> Result:
        """
        Writes the result to a location in S3 and returns the resulting URI.

        Args:
            - value_ (Any): the value to write; will then be stored as the `value` attribute
                of the returned `Result` instance
            - **kwargs (optional): if provided, will be used to format the location template
                to determine the location to write to

        Returns:
            - Result: a new Result instance with the appropriately formatted S3 URI
        """

        new = self.format(**kwargs)
        new.value = value_
        self.logger.debug("Starting to upload result to {}...".format(new.location))
        binary_data = new.serializer.serialize(new.value)

        stream = io.BytesIO(binary_data)

        # upload
        from botocore.exceptions import ClientError

        try:
            self.client.upload_fileobj(stream, Bucket=self.bucket, Key=new.location)
        except ClientError as err:
            self.logger.error("Error uploading to S3: {}".format(err))
            raise err

        self.logger.debug("Finished uploading result to {}.".format(new.location))
        return new

    def read(self, location: str) -> Result:
        """
        Reads a result from S3, reads it and returns a new `Result` object with the
        corresponding value.

        Args:
            - location (str): the S3 URI to read from

        Returns:
            - Any: the read result
        """
        new = self.copy()
        new.location = location

        try:
            self.logger.debug("Starting to download result from {}...".format(location))
            stream = io.BytesIO()

            # download - uses `self` in case the client is already instantiated
            self.client.download_fileobj(
                Bucket=self.bucket, Key=location, Fileobj=stream
            )

            try:
                new.value = new.serializer.deserialize(stream.getvalue())
            except EOFError:
                new.value = None
            self.logger.debug("Finished downloading result from {}.".format(location))

        except Exception as exc:
            self.logger.exception(
                "Unexpected error while reading from result handler: {}".format(
                    repr(exc)
                )
            )
            raise exc

        return new

    def exists(self, location: str, **kwargs: Any) -> bool:
        """
        Checks whether the target result exists in the S3 bucket.

        Does not validate whether the result is `valid`, only that it is present.

        Args:
            - location (str): Location of the result in the specific result target.
            - **kwargs (Any): string format arguments for `location`

        Returns:
            - bool: whether or not the target result exists.
        """
        import botocore

        try:
            self.client.get_object(Bucket=self.bucket, Key=location.format(**kwargs))
        except botocore.exceptions.ClientError as exc:
            if exc.response["Error"]["Code"] == "NoSuchKey":
                return False
            raise
        except Exception as exc:
            self.logger.exception(
                "Unexpected error while reading from S3: {}".format(repr(exc))
            )
            raise
        return True
