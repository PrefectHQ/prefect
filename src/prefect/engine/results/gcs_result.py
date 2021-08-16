from typing import Any, TYPE_CHECKING

from prefect.engine.result.base import Result

if TYPE_CHECKING:
    import google.cloud


class GCSResult(Result):
    """
    Result that is written to and read from a Google Cloud Bucket.

    To authenticate with Google Cloud, you need to ensure that your flow's runtime environment
    has the proper credentials available (see
    https://cloud.google.com/docs/authentication/production for all the authentication
    options).

    You can also optionally provide your service account key to
    `prefect.context.secrets.GCP_CREDENTIALS` for automatic authentication - see [Third Party
    Authentication](../../../orchestration/recipes/third_party_auth.html) for more information.

    To read more about service account keys see
    https://cloud.google.com/iam/docs/creating-managing-service-account-keys.  To read more
    about the JSON representation of service account keys see
    https://cloud.google.com/iam/docs/reference/rest/v1/projects.serviceAccounts.keys.

    Args:
        - bucket (str): the name of the bucket to write to / read from
        - **kwargs (Any, optional): any additional `Result` initialization options
    """

    def __init__(self, bucket: str = None, **kwargs: Any) -> None:
        self.bucket = bucket
        super().__init__(**kwargs)

    @property
    def gcs_bucket(self) -> "google.cloud.storage.bucket.Bucket":
        if not hasattr(self, "_gcs_bucket"):
            from prefect.utilities.gcp import get_storage_client

            client = get_storage_client()
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

    def write(self, value_: Any, **kwargs: Any) -> Result:
        """
        Writes the result value to a location in GCS and returns the resulting URI.

        Args:
            - value_ (Any): the value to write; will then be stored as the `value` attribute
                of the returned `Result` instance
            - **kwargs (optional): if provided, will be used to format the location template
                to determine the location to write to

        Returns:
            - Result: a new Result instance with the appropriately formatted location
        """

        new = self.format(**kwargs)
        new.value = value_
        self.logger.debug("Starting to upload result to {}...".format(new.location))
        binary_data = new.serializer.serialize(new.value)

        self.gcs_bucket.blob(new.location).upload_from_string(binary_data)
        self.logger.debug("Finished uploading result to {}.".format(new.location))

        return new

    def read(self, location: str) -> Result:
        """
        Reads a result from a GCS bucket and returns a corresponding `Result` instance.

        Args:
            - location (str): the GCS URI to read from

        Returns:
            - Result: the read result
        """
        new = self.copy()
        new.location = location

        try:
            self.logger.debug("Starting to download result from {}...".format(location))
            blob = self.gcs_bucket.blob(location)
            # Support GCS < 1.31
            serialized_value = (
                blob.download_as_bytes()
                if hasattr(blob, "download_as_bytes")
                else blob.download_as_string()
            )
            try:
                new.value = new.serializer.deserialize(serialized_value)
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
        Checks whether the target result exists.

        Does not validate whether the result is `valid`, only that it is present.

        Args:
            - location (str): Location of the result in the specific result target.
                Will check whether the provided location exists
            - **kwargs (Any): string format arguments for `location`

        Returns:
            - bool: whether or not the target result exists.
        """
        return self.gcs_bucket.blob(location.format(**kwargs)).exists()
