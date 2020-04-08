from typing import Any, TYPE_CHECKING

from prefect.engine.result.base import Result
from prefect.client import Secret
from prefect.utilities import logging

if TYPE_CHECKING:
    import google.cloud


class GCSResult(Result):
    """
    Result that is written to and read from a Google Cloud Bucket.

    To authenticate with Google Cloud, you need to ensure that your flow's
    runtime environment has the proper credentials available
    (see https://cloud.google.com/docs/authentication/production for all the authentication options).

    You can also optionally provide the name of a Prefect Secret containing your
    service account key. To read more about service account keys see https://cloud.google.com/iam/docs/creating-managing-service-account-keys.
    To read more about the JSON representation of service account keys see https://cloud.google.com/iam/docs/reference/rest/v1/projects.serviceAccounts.keys.

    Args:
        - value (Any, optional): the value of the result
        - bucket (str): the name of the bucket to write to / read from
        - credentials_secret (str, optional): the name of the Prefect Secret
            which stores a JSON representation of your Google Cloud credentials.
        - **kwargs (Any, optional): any additional `Result` initialization options
    """

    def __init__(
        self,
        value: Any = None,
        bucket: str = None,
        credentials_secret: str = None,
        **kwargs: Any
    ) -> None:
        self.bucket = bucket
        self.credentials_secret = credentials_secret
        self.logger = logging.get_logger(type(self).__name__)
        super().__init__(value, **kwargs)

    @property
    def gcs_bucket(self) -> "google.cloud.storage.bucket.Bucket":
        if not hasattr(self, "_gcs_bucket"):
            from prefect.utilities.gcp import get_storage_client

            if self.credentials_secret:
                credentials = Secret(self.credentials_secret).get()
            else:
                credentials = None
            client = get_storage_client(credentials=credentials)
            self.gcs_bucket = client.bucket(self.bucket)
        return self._gcs_bucket

    @gcs_bucket.setter
    def gcs_bucket(self, val: Any) -> None:
        self._gcs_bucket = val

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        if "_gcs_bucket" in state:
            del state["_gcs_bucket"]
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)

    def write(self) -> str:
        """
        Writes the result value to a location in GCS and returns the resulting URI.

        Returns:
            - str: the GCS URI
        """

        if not self._rendered_filepath:
            raise ValueError("Must call `Result.format()` first")

        self.logger.debug(
            "Starting to upload result to {}...".format(self._rendered_filepath)
        )
        binary_data = self.serialize().decode()

        self.gcs_bucket.blob(self._rendered_filepath).upload_from_string(binary_data)
        self.logger.debug(
            "Finished uploading result to {}.".format(self._rendered_filepath)
        )

        return self._rendered_filepath

    def read(self, loc: str = None) -> Any:
        """
        Reads a result from a GCS bucket

        Args:
            - loc (str, optional): the GCS URI

        Returns:
            - Any: the read result
        """
        uri = loc or self._rendered_filepath

        if not uri:
            raise ValueError("Must call `Result.format()` first")

        try:
            self.logger.debug("Starting to download result from {}...".format(uri))
            serialized_value = self.gcs_bucket.blob(uri).download_as_string()
            try:
                self.value = self.deserialize(serialized_value)
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
        Checks whether the target result exists.

        Does not validate whether the result is `valid`, only that it is present.

        Returns:
            - bool: whether or not the target result exists.
        """
        if not self._rendered_filepath:
            raise ValueError("Must call `Result.format()` first")
        return self.gcs_bucket.blob(self._rendered_filepath).exists()
