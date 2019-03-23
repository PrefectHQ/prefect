"""
Result Handlers provide the hooks that Prefect uses to store task results in production; a `ResultHandler` can be provided to a `Flow` at creation.

Anytime a task needs its output or inputs stored, a result handler is used to determine where this data should be stored (and how it can be retrieved).
"""
import base64
import tempfile
from typing import Any, Optional

import cloudpickle

from prefect import config
from prefect.client.client import Client
from prefect.engine.result_handlers import ResultHandler


class CloudResultHandler(ResultHandler):
    """
    Hook for storing and retrieving task results from Prefect cloud storage.

    Args:
        - result_handler_service (str, optional): the location of the service
            which will further process and store the results; if not provided, will default to
            the value of `cloud.result_handler` in your config file
    """

    def __init__(self, result_handler_service: str = None) -> None:
        self._client = None  # type: Optional[Client]
        if result_handler_service is None:
            self.result_handler_service = config.cloud.result_handler
        else:
            self.result_handler_service = result_handler_service
        super().__init__()

    def _initialize_client(self) -> None:
        """
        Helper method for ensuring that CloudHandlers which are initialized locally
        do not attempt to start a Client.  This is important because CloudHandlers are
        currently attached to `Flow` objects which need to be serialized / deserialized
        independently of cloud settings.

        This will instantiate a Client upon the first call to (de)serialize.
        """
        if self._client is None:
            self._client = Client()

    def read(self, uri: str) -> Any:
        """
        Read a result from the given URI location.

        Args:
            - uri (str): the path to the location of a result

        Returns:
            - the deserialized result from the provided URI
        """
        self._initialize_client()

        self.logger.debug("Starting to read result from {}...".format(uri))
        res = self._client.get(  # type: ignore
            "/", server=self.result_handler_service, **{"uri": uri}
        )

        try:
            return_val = cloudpickle.loads(base64.b64decode(res.get("result", "")))
        except EOFError:
            return_val = None
        self.logger.debug("Finished reading result from {}...".format(uri))

        return return_val

    def write(self, result: Any) -> str:
        """
        Write the provided result to Prefect Cloud.

        Args:
            - result (Any): the result to store

        Returns:
            - str: the URI path to the result in Cloud storage
        """
        self._initialize_client()

        binary_data = base64.b64encode(cloudpickle.dumps(result)).decode()
        self.logger.debug(
            "Starting to upload result to {}...".format(self.result_handler_service)
        )
        res = self._client.post(  # type: ignore
            "/", server=self.result_handler_service, **{"result": binary_data}
        )
        self.logger.debug(
            "Finished uploading result to {}...".format(self.result_handler_service)
        )
        return res.get("uri", "")
