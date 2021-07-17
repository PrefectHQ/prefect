from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, get_type_hints

import fastapi

from prefect.orion.utilities.database import OrionAsyncSession


async def get_session():
    """
    Dependency-injected database session.

    The context manager will automatically handle commits,
    rollbacks, and closing the connection.
    """
    async with OrionAsyncSession.begin() as session:
        yield session


class OrionRouter(fastapi.APIRouter):
    """
    Allows API routers to use type annotations for `response_model` if not
    provided explicitly. Inspired by https://github.com/dmontagu/fastapi-utils.
    """

    def add_api_route(
        self, path: str, endpoint: Callable[..., Any], **kwargs: Any
    ) -> None:
        if kwargs.get("response_model") is None:
            kwargs["response_model"] = get_type_hints(endpoint).get("return")
        return super().add_api_route(path, endpoint, **kwargs)
