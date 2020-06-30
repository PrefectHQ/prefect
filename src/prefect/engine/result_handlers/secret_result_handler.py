from typing import Any

import prefect
from prefect.engine.result_handlers import ResultHandler


class SecretResultHandler(ResultHandler):
    """
    Hook for storing and retrieving sensitive task results from a Secret store. Only intended
    to be used for Secret tasks.

    Args:
        - secret_task (Task): the Secret Task that this result handler will be used for
    """

    def __init__(self, secret_task: "prefect.tasks.secrets.Secret") -> None:
        self.secret_task = secret_task
        super().__init__()

    def read(self, name: str) -> Any:
        """
        Read a secret from a provided name with the provided Secret class;
        this method actually retrieves the secret from the Secret store.

        Args:
            - name (str): the name of the secret to retrieve

        Returns:
            - Any: the deserialized result
        """
        return self.secret_task.run()  # type: ignore

    def write(self, result: Any) -> str:
        """
        Returns the name of the secret.

        Args:
            - result (Any): the result to write

        Returns:
            - str: the JSON representation of the result
        """
        return self.secret_task.name
