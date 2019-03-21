import json
from typing import Any

from prefect.engine.result_handlers import ResultHandler


class JSONResultHandler(ResultHandler):
    """
    Hook for storing and retrieving task results to / from JSON. Only intended to be used
    for small data loads.
    """

    def read(self, jblob: str) -> Any:
        """
        Read a result from a string JSON blob.

        Args:
            - jblob (str): the JSON representation of the result

        Returns:
            - Any: the deserialized result
        """
        return json.loads(jblob)

    def write(self, result: Any) -> str:
        """
        Serialize the provided result to JSON.

        Args:
            - result (Any): the result to write

        Returns:
            - str: the JSON representation of the result
        """
        return json.dumps(result)
