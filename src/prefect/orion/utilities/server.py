"""
Utilities for the Orion API server.
"""
import functools
import inspect
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, Callable, Coroutine, get_type_hints

from fastapi import APIRouter, Request, Response, status
from fastapi.routing import APIRoute


def response_scoped_dependency(dependency: Callable):
    """
    Uses an async stack that is exited before the response is returned to a client to
    ensure a dependency is closed. This is particularly useful for database sesssions
    which must be committed before the client can do more work.

    Args:
        dependency: An async callable which consumes the `fastapi.Request` object.
            Additional FastAPI dependencies may be included as well.

    Returns:
        A wrapped `dependency` which will push the `dependency` context manager onto
        a stack when called.
    """

    async def wrapper(*args, __request__: Request, **kwargs):
        # Replicate FastAPI behavior of auto-creating a context manager
        if inspect.isasyncgenfunction(dependency):
            context_manager = asynccontextmanager(dependency)
        else:
            context_manager = dependency

        # Enter the special stack
        return (
            await __request__.state.response_scoped_depends_stack.enter_async_context(
                context_manager(*args, **kwargs)
            )
        )

    # Generate a new signature
    signature = inspect.signature(dependency)
    new_parameters = signature.parameters.copy()
    request_parameter = inspect.signature(wrapper).parameters["__request__"]
    new_parameters["__request__"] = request_parameter
    functools.update_wrapper(wrapper, dependency)
    wrapper.__signature__ = signature.replace(parameters=tuple(new_parameters.values()))

    return wrapper


class OrionAPIRoute(APIRoute):
    """
    A FastAPI APIRoute class which inserts a special stack on requests.

    Requests have `request.scope.astack` which is an async stack for the entire scope
    of the request. However, if you want to close a dependency before the request is
    complete (i.e. before returning a response to the user), we need a stack with a
    different scope.
    """

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        default_handler = super().get_route_handler()

        async def handle_response_scoped_depends(request: Request) -> Response:
            async with AsyncExitStack() as stack:
                # Create a new stack scoped to exit before the response is returned
                request.state.response_scoped_depends_stack = stack
                response = await default_handler(request)

            return response

        return handle_response_scoped_depends


class OrionRouter(APIRouter):
    """
    A base class for Orion API routers.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("route_class", OrionAPIRoute)
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
            # explicilty set a response_class that will handle status codes
            # and not return anything in the body
            kwargs["response_class"] = Response
        if kwargs.get("response_model") is None:
            kwargs["response_model"] = get_type_hints(endpoint).get("return")
        return super().add_api_route(path, endpoint, **kwargs)
