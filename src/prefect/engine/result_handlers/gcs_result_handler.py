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

    def serialize(self, result: Any) -> str:
        """
        Given a result, serializes the result and writes to a location in GCS
        and returns the resulting URI.

        Args:
            - result (Any): the serialized result

        Returns:
            - str: the GCS URI
        """
        uri = f"{pendulum.now('utc').format('Y/M/D')}/{uuid.uuid4()}.prefect_result"
        self.logger.debug(f"Starting to upload result to {uri}...")
        binary_data = base64.b64encode(cloudpickle.dumps(result)).decode()
        self.bucket.blob(f"{uri}").upload_from_string(binary_data)
        self.logger.debug(f"Finished uploading result to {uri}.")
        return uri

    def deserialize(self, uri: str) -> Any:
        """
        Given a uri, reads a result from GCS, deserializes it and returns it

        Args:
            - uri (str): the GCS URI

        Returns:
            - Any: the deserialized result
        """
        try:
            self.logger.debug(f"Starting to download result from {uri}...")
            result = self.bucket.blob(f"{uri}").download_as_string()
            try:
                return_val = cloudpickle.loads(base64.b64decode(result))
            except EOFError:
                return_val = None
            self.logger.debug(f"Finished downloading result from {uri}.")
        except Exception as exc:
            self.logger.error(exc)
            return_val = None
        return return_val
