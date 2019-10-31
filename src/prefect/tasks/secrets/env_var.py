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
        - raise_if_missing (bool): if True, an error will be raised if the env var is not found.
        - **kwargs (Any, optional): additional keyword arguments to pass to the Task constructor
    """

    def __init__(
        self,
        env_var: str,
        name: str = None,
        cast: Callable[[Any], Any] = None,
        raise_if_missing: bool = False,
        **kwargs
    ):
        self.env_var = env_var
        self.cast = cast
        self.raise_if_missing = raise_if_missing
        if name is None:
            name = env_var

        super().__init__(name=name, **kwargs)

    def run(self):
        """
        Returns the value of an environment variable after applying an optional `cast` function.

        Returns:
            - Any: the (optionally type-cast) value of the environment variable
        """
        if self.raise_if_missing and self.env_var not in os.environ:
            raise ValueError("Environment variable not set: {}".format(self.env_var))
        value = os.getenv(self.env_var)
        if value is not None and self.cast is not None:
            value = self.cast(value)
        return value
