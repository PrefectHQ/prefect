import json

from typing import Any

import prefect
from prefect.engine.result import Result


class SecretResult(Result):
    """
    Hook for storing and retrieving sensitive task results from a Secret store. Only
    intended to be used for Secret Tasks - each call to "read" will actually rerun
    the underlying secret task and re-retrieve the secret value.

    Args:
        - value (Any): the underlying value this Result should represent
    """

    def __init__(
        self, secret_task: "prefect.tasks.secrets.Secret", **kwargs: Any
    ) -> None:
        self.secret_task = secret_task
        super().__init__(**kwargs)

    def read(self, filepath: str) -> Result:
        """
        Returns the Secret Value corresponding to the passed name.

        Args:
            - filepath (str): the name of the Secret to retrieve

        Returns:
            - Result: a new result instance with the data represented by the filepath
        """
        new = self.copy()
        new.value = self.secret_task.run(name=filepath)
        new.filepath = filepath
        return new

    def write(self, value: Any, **kwargs: Any) -> Result:
        """
        .value` and returns `self`.

        Args:
            - value (Any): unused, for interface compatibility
            - **kwargs (optional): unused, for interface compatibility

        Raises:
            - ValueError: SecretResults cannot be written to
        """
        raise ValueError("SecretResults cannot be written to.")

    def exists(self, filepath: str) -> bool:
        """
        Confirms that the provided value is JSON deserializable.

        Args:
            - filepath (str): the value to test

        Returns:
            - bool: whether the provided string can be deserialized
        """
        return True
