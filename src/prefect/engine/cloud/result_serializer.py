"""
Result Handlers provide the hooks that Prefect uses to store task results in production; a `ResultSerializer` can be provided to a `Flow` at creation.

Anytime a task needs its output or inputs stored, a result handler is used to determine where this data should be stored (and how it can be retrieved).
"""
import base64
import tempfile
from typing import Any

import cloudpickle

from prefect import config
from prefect.client.client import Client
from prefect.engine.result_serializers import ResultSerializer


class CloudResultSerializer(ResultSerializer):
    """
    Hook for storing and retrieving task results from Prefect cloud storage.

    Args:
        - result_serializer_service (str, optional): the location of the service
            which will further process and store the results; if not provided, will default to
            the value of `cloud.result_serializer` in your config file
    """

    def __init__(self, result_serializer_service: str = None) -> None:
        self.client = None
        self.result_serializer_service = result_serializer_service
        super().__init__()

    def _initialize_client(self) -> None:
        """
        Helper method for ensuring that CloudHandlers which are initialized locally
        do not attempt to start a Client.  This is important because CloudHandlers are
        currently attached to `Flow` objects which need to be serialized / deserialized
        independently of cloud settings.

        This will instantiate a Client upon the first call to (de)serialize.
        """
        if self.client is None:
            self.client = Client()  # type: ignore
        if self.result_serializer_service is None:
            self.result_serializer_service = config.cloud.result_serializer

    def deserialize(self, uri: str) -> Any:
        """
        Deserialize a result from the given URI location.

        Args:
            - uri (str): the path to the location of a serialized result

        Returns:
            - the deserialized result from the provided URI
        """
        self._initialize_client()
        self.logger.debug("Starting to read result from {}...".format(uri))
        res = self.client.get(  # type: ignore
            "/", server=self.result_serializer_service, **{"uri": uri}
        )

        try:
            return_val = cloudpickle.loads(base64.b64decode(res.get("result", "")))
        except EOFError:
            return_val = None
        self.logger.debug("Finished reading result from {}...".format(uri))

        return return_val

    def serialize(self, result: Any) -> str:
        """
        Serialize the provided result to Prefect Cloud.

        Args:
            - result (Any): the result to serialize and store

        Returns:
            - str: the URI path to the serialized result in Cloud storage
        """
        self._initialize_client()
        binary_data = base64.b64encode(cloudpickle.dumps(result)).decode()
        self.logger.debug(
            "Starting to upload result to {}...".format(self.result_serializer_service)
        )
        res = self.client.post(  # type: ignore
            "/", server=self.result_serializer_service, **{"result": binary_data}
        )
        self.logger.debug(
            "Finished uploading result to {}...".format(self.result_serializer_service)
        )
        return res.get("uri", "")
