from typing import Any, cast

import prefect
from prefect.engine.result import Result


class ResourceResult(Result):
    """A result for Resource objects.

    Resource objects are never written or read from anywhere, this interface
    only exists to enable support for resource objects in an active flow run.

    Args:
        - **kwargs (Any, optional): any additional `Result` initialization options
    """

    def __init__(self, **kwargs: Any) -> None:
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

    @property  # type: ignore
    def value(self) -> Any:  # type: ignore
        if self.handle is None:
            raise ValueError("No value found for this result")
        return self.handle.get()

    @value.setter
    def value(self, val: Any) -> None:
        pass

    def from_value(self, value: Any) -> "ResourceResult":
        """
        Create a new copy of the result object with the provided value.

        Args:
            - value (ResourceHandle or None): the value to use

        Returns:
            - ResourceResult: a new ResourceResult instance with the given value
        """
        if not (
            value is None
            or isinstance(value, prefect.tasks.resources.base.ResourceHandle)
        ):
            raise TypeError(f"value must be a ResourceHandle or None, got `{value}`")
        new = cast(ResourceResult, self.copy())
        new.location = None
        new.handle = value  # type: ignore
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
