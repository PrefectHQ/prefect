import os
from typing import Any, Callable

from prefect.tasks.secrets import Secret


class EnvVarSecret(Secret):
    """
    A `Secret` task that retrieves a value from an environment variable.

    Args:
        - env_var (str): the environment variable that contains the secret value
        - name (str, optional): a name for the task. If not provided, `env_var` is used.
        - cast (Callable[[Any], Any]): A function that will be called on the Parameter
            value to coerce it to a type.
        - **kwargs (Any, optional): additional keyword arguments to pass to the Task constructor

    Raises:
        - ValueError: if a `result_handler` keyword is passed
    """

    def __init__(
        self,
        env_var: str,
        name: str = None,
        cast: Callable[[Any], Any] = None,
        **kwargs
    ):
        self.env_var = env_var
        self.cast = cast
        if name is None:
            name = env_var

        super().__init__(name=name, **kwargs)

    def run(self):
        """
        Returns the value of an environment variable after applying an optional `cast` function.

        Returns:
            - Any: the (optionally type-cast) value of the environment variable
        """
        value = os.getenv(self.env_var)
        if value is not None and self.cast is not None:
            value = self.cast(value)
        return value
