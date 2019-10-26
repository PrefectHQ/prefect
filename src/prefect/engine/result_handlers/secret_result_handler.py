import json
from typing import Any

from prefect.engine.result_handlers import ResultHandler


class SecretResultHandler(ResultHandler):
    """
    Hook for storing and retrieving sensitive task results from a Secret store. Only intended to be used
    for Secret tasks.
    """
    def __init__(self, secret_task):
        super().__init__()

    def read(self, jblob: str) -> Any:
        """
        Read a secret from a provided name with the provided Secret class;
        this method actually retrieves the secret from the Secret store.

        Args:
            - jblob (str): the JSON representation of the result

        Returns:
            - Any: the deserialized result
        """
        return json.loads(jblob)

    def write(self, result: Any) -> str:
        """
        Returns the name of the secret.

        Args:
            - result (Any): the result to write

        Returns:
            - str: the JSON representation of the result
        """
        return json.dumps(result)
