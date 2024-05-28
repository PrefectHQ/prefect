"""
Utilities for the Prefect REST API server.
"""

from contextlib import AsyncExitStack
from typing import Any, Callable, Coroutine, Sequence, Set, get_type_hints

from fastapi import APIRouter, Request, Response, status
from fastapi.routing import APIRoute, BaseRoute
from starlette.routing import Route as StarletteRoute


def method_paths_from_routes(routes: Sequence[BaseRoute]) -> Set[str]:
    """
    Generate a set of strings describing the given routes in the format: <method> <path>

    For example, "GET /logs/"
    """
    method_paths = set()
    for route in routes:
        if isinstance(route, (APIRoute, StarletteRoute)):
            for method in route.methods:
                method_paths.add(f"{method} {route.path}")

    return method_paths


class PrefectAPIRoute(APIRoute):
    """
    A FastAPIRoute class which attaches an async stack to requests that exits before
    a response is returned.

    Requests already have `request.scope['fastapi_astack']` which is an async stack for
    the full scope of the request. This stack is used for managing contexts of FastAPI
    dependencies. If we want to close a dependency before the request is complete
    (i.e. before returning a response to the user), we need a stack with a different
    scope. This extension adds this stack at `request.state.response_scoped_stack`.
    """

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        default_handler = super().get_route_handler()

        async def handle_response_scoped_depends(request: Request) -> Response:
            # Create a new stack scoped to exit before the response is returned
            async with AsyncExitStack() as stack:
                request.state.response_scoped_stack = stack
                response = await default_handler(request)

            return response

        return handle_response_scoped_depends


class PrefectRouter(APIRouter):
    """
    A base class for Prefect REST API routers.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("route_class", PrefectAPIRoute)
        super().__init__(**kwargs)

    def add_api_route(
        self, path: str, endpoint: Callable[..., Any], **kwargs: Any
    ) -> None:
        """
        Add an API route.

        For routes that return content and have not specified a `response_model`,
        use return type annotation to infer the response model.

        For routes that return No-Content status codes, explicitly set
        a `response_class` to ensure nothing is returned in the response body.
        """
        if kwargs.get("status_code") == status.HTTP_204_NO_CONTENT:
            # any routes that return No-Content status codes must
            # explicitly set a response_class that will handle status codes
            # and not return anything in the body
            kwargs["response_class"] = Response
        if kwargs.get("response_model") is None:
            kwargs["response_model"] = get_type_hints(endpoint).get("return")
        return super().add_api_route(path, endpoint, **kwargs)
