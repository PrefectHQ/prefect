from typing import Any

import prefect
from prefect.engine.result import Result


class SecretResult(Result):
    """
    Hook for storing and retrieving sensitive task results from a Secret store. Only
    intended to be used for Secret Tasks - each call to "read" will actually rerun
    the underlying secret task and re-retrieve the secret value.

    Args:
        - secret_task (Task): the Secret Task this result wraps
        - **kwargs (Any, optional): additional kwargs to pass to the `Result` initialization
    """

    def __init__(
        self, secret_task: "prefect.tasks.secrets.Secret", **kwargs: Any
    ) -> None:
        self.secret_task = secret_task
        kwargs.setdefault("location", secret_task.name)
        super().__init__(**kwargs)

    def read(self, location: str) -> Result:
        """
        Returns the Secret Value corresponding to the passed name.

        Args:
            - location (str): the name of the Secret to retrieve

        Returns:
            - Result: a new result instance with the data represented by the location
        """
        new = self.copy()
        new.value = self.secret_task.run(name=location)
        new.location = location
        return new

    def write(self, value: Any, **kwargs: Any) -> Result:
        """
        Secret results cannot be written to; provided for interface compatibility.

        Args:
            - value (Any): unused, for interface compatibility
            - **kwargs (optional): unused, for interface compatibility

        Raises:
            - ValueError: SecretResults cannot be written to
        """
        raise ValueError("SecretResults cannot be written to.")
