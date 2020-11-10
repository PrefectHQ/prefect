import os
from typing import Any, Callable

from prefect.tasks.secrets import PrefectSecret


class EnvVarSecret(PrefectSecret):
    """
    A `Secret` task that retrieves a value from an environment variable.

    Args:
        - name (str, optional): the environment variable that contains the secret value
        - cast (Callable[[Any], Any]): A function that will be called on the Parameter
            value to coerce it to a type.
        - raise_if_missing (bool): if True, an error will be raised if the env var is not found.
        - **kwargs (Any, optional): additional keyword arguments to pass to the Task constructor
    """

    def __init__(
        self,
        name: str = None,
        cast: Callable[[Any], Any] = None,
        raise_if_missing: bool = False,
        **kwargs
    ):
        self.secret_name = name
        self.cast = cast
        self.raise_if_missing = raise_if_missing
        super().__init__(name=name, **kwargs)

    def run(self, name: str = None):
        """
        Returns the value of an environment variable after applying an optional `cast` function.

        Args:
            - name (str, optional): the name of the underlying environment variable to
                retrieve. Defaults to the name provided at initialization.

        Returns:
            - Any: the (optionally type-cast) value of the environment variable

        Raises:
            - ValueError: if `raise_is_missing` is `True` and the environment variable was not found
        """
        if name is None:
            name = self.secret_name
        if name is None:
            raise ValueError("A secret name must be provided.")
        if self.raise_if_missing and name not in os.environ:
            raise ValueError("Environment variable not set: {}".format(name))
        value = os.getenv(name)
        if value is not None and self.cast is not None:
            value = self.cast(value)
        return value
