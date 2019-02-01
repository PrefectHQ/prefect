# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import json
from typing import Any

from prefect.engine.result_serializers import ResultSerializer


class JSONResultSerializer(ResultSerializer):
    """
    Hook for storing and retrieving task results to / from JSON. Only intended to be used
    for small data loads.
    """

    def deserialize(self, jblob: str) -> Any:
        """
        Deserialize a result from a string JSON blob.

        Args:
            - jblob (str): the JSON representation of the result

        Returns:
            - the deserialized result
        """
        return json.loads(jblob)

    def serialize(self, result: Any) -> str:
        """
        Serialize the provided result to JSON.

        Args:
            - result (Any): the result to serialize

        Returns:
            - str: the JSON representation of the result
        """
        return json.dumps(result)
