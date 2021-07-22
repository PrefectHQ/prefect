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
