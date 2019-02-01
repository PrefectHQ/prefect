import base64
import cloudpickle
import pendulum
import uuid

from google.cloud import storage
from typing import Any

from prefect.engine.result_handlers import ResultHandler


class GCSResultHandler(ResultHandler):
    """
    Result Handler for serializing to and from a Google Cloud Bucket.

    Args:
        - bucket (str): the name of the bucket to write to / read from

    Note that for this result handler to work properly, your Google Application Credentials
    must be made available.
    """

    def __init__(self, bucket: str = None) -> None:
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket)
        super().__init__()

    def write(self, result: Any) -> str:
        """
        Given a result, writes the result and writes to a location in GCS
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
        self.bucket.blob(uri).upload_from_string(binary_data)
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
            result = self.bucket.blob(uri).download_as_string()
            try:
                return_val = cloudpickle.loads(base64.b64decode(result))
            except EOFError:
                return_val = None
            self.logger.debug("Finished downloading result from {}.".format(uri))
        except Exception as exc:
            self.logger.error(exc)
            return_val = None
        return return_val
