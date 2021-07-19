from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, get_type_hints

import fastapi


class OrionRouter(fastapi.APIRouter):
    """
    Allows API routers to use return type annotations for their
    `response_model` if not provided explicitly.
    """

    def add_api_route(
        self, path: str, endpoint: Callable[..., Any], **kwargs: Any
    ) -> None:
        if kwargs.get("response_model") is None:
            kwargs["response_model"] = get_type_hints(endpoint).get("return")
        return super().add_api_route(path, endpoint, **kwargs)


class AutoEnum(Enum):
    """An enum class that automatically generates values
    from variable names. This guards against common errors
    where variable names are updated but values are not.

    See https://docs.python.org/3/library/enum.html#using-automatic-values

    Example:
            >>> from enum import auto
            >>> class MyEnum(AutoEnum):
            ...     red = auto() # equivalent to red = 'red'
            ...     blue = auto() # equivalent to blue = 'blue'
            ...
    """

    def _generate_next_value_(name, start, count, last_values):
        return name
