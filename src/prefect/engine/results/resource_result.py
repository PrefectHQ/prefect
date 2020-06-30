from typing import Any

import prefect
from prefect.engine.result import Result


class ResourceResult(Result):
    def __init__(self, **kwargs):
        if "serializer" in kwargs:
            raise ValueError("Can't pass a serializer to a ResourceResult.")
        self.handle = None
        super().__init__(**kwargs)

    def read(self, location: str) -> Result:
        """
        Will return the underlying value regardless of the argument passed.

        Args:
            - location (str): an unused argument
        """
        return self

    @property
    def value(self):
        if self.handle is None:
            raise ValueError("No value found for this result")
        return self.handle.get()

    @value.setter
    def value(self, val):
        pass

    def from_value(self, value: Any) -> "Result":
        if not (
            value is None or isinstance(value, prefect.core.resources.ResourceHandle)
        ):
            raise TypeError(f"value must be a ResourceHandle or None, got `{value}`")
        new = self.copy()
        new.location = None
        new.handle = value
        return new

    def write(self, value: Any, **kwargs: Any) -> Result:
        """
        Not supported, here for interface compatibility only.

        Args:
            - value (Any): unused, for interface compatibility
            - **kwargs (optional): unused, for interface compatibility

        Raises:
            - ValueError: ResourceResult cannot be written to
        """
        raise ValueError("ResourceResult cannot be written to.")

    def exists(self, location: str, **kwargs: Any) -> bool:
        """
        Checks whether the target result exists.

        Always returns True for ResourceResult.

        Args:
            - location (str, optional): Location of the result in the specific result target.
            - **kwargs (Any): string format arguments for `location`

        Returns:
            - bool: whether the result exists, always True.
        """
        return True
