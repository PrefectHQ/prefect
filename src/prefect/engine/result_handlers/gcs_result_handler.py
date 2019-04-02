import base64
import uuid
from typing import Any, TYPE_CHECKING

import cloudpickle
import pendulum

from prefect.client import Secret
from prefect.engine.result_handlers import ResultHandler


if TYPE_CHECKING:
    import google.cloud


class GCSResultHandler(ResultHandler):
    """
    Result Handler for writing to and reading from a Google Cloud Bucket.

    Args:
        - bucket (str): the name of the bucket to write to / read from

    Note that for this result handler to work properly, your Google Application Credentials
    must be made available.
    """

    def __init__(self, bucket: str = None) -> None:
        self.bucket = bucket
        self.initialize_client()
        super().__init__()

    def initialize_client(self) -> None:
        """
        Initializes GCS connections.
        """
        from google.oauth2.service_account import Credentials
        from google.cloud import storage

        creds = Secret("GOOGLE_APPLICATION_CREDENTIALS").get()
        credentials = Credentials.from_service_account_info(creds)
        project = credentials.project_id
        client = storage.Client(project=project, credentials=credentials)
        self.gcs_bucket = client.bucket(self.bucket)

    @property
    def gcs_bucket(self) -> "google.cloud.storage.bucket.Bucket":
        if not hasattr(self, "_gcs_bucket"):
            self.initialize_client()
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

    def write(self, result: Any) -> str:
        """
        Given a result, writes the result to a location in GCS
        and returns the resulting URI.

        Args:
            - result (Any): the written result

        Returns:
            - str: the GCS URI
        """
        date = pendulum.now("utc").format("Y/M/D")
        uri = "{date}/{uuid}.prefect_result".format(date=date, uuid=uuid.uuid4())
        self.logger.debug("Starting to upload result to {}...".format(uri))
        binary_data = base64.b64encode(cloudpickle.dumps(result)).decode()
        self.gcs_bucket.blob(uri).upload_from_string(binary_data)
        self.logger.debug("Finished uploading result to {}.".format(uri))
        return uri

    def read(self, uri: str) -> Any:
        """
        Given a uri, reads a result from GCS, reads it and returns it

        Args:
            - uri (str): the GCS URI

        Returns:
            - Any: the read result
        """
        try:
            self.logger.debug("Starting to download result from {}...".format(uri))
            result = self.gcs_bucket.blob(uri).download_as_string()
            try:
                return_val = cloudpickle.loads(base64.b64decode(result))
            except EOFError:
                return_val = None
            self.logger.debug("Finished downloading result from {}.".format(uri))
        except Exception as exc:
            self.logger.error(exc)
            return_val = None
        return return_val
