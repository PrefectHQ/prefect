"""
Utilities for the Orion API server.
"""
import functools
import inspect
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, Callable, Coroutine, Iterable, Set, get_type_hints

from fastapi import APIRouter, Request, Response, status
from fastapi.routing import APIRoute


def method_paths_from_routes(routes: Iterable[APIRoute]) -> Set[str]:
    """
    Generate a set of strings describing the given routes in the format: <method> <path>

    For example, "GET /logs/"
    """
    method_paths = set()
    for route in routes:
        for method in route.methods:
            method_paths.add(f"{method} {route.path}")

    return method_paths


def response_scoped_dependency(dependency: Callable):
    """
    Ensure that this dependency closes before the response is returned to the client. By
    default, FastAPI closes dependencies after sending the response.

    Uses an async stack that is exited before the response is returned. This is
    particularly useful for database sesssions which must be committed before the client
    can do more work.

    NOTE: Do not use a response-scoped dependency within a FastAPI background task.
          Background tasks run after FastAPI sends the response, so a response-scoped
          dependency will already be closed. Use a normal FastAPI dependency instead.

    Args:
        dependency: An async callable. FastAPI dependencies may still be used.

    Returns:
        A wrapped `dependency` which will push the `dependency` context manager onto
        a stack when called.
    """
    signature = inspect.signature(dependency)

    async def wrapper(*args, request: Request, **kwargs):
        # Replicate FastAPI behavior of auto-creating a context manager
        if inspect.isasyncgenfunction(dependency):
            context_manager = asynccontextmanager(dependency)
        else:
            context_manager = dependency

        # Ensure request is provided if requested
        if "request" in signature.parameters:
            kwargs["request"] = request

        # Enter the route handler provided stack that is closed before responding,
        # return the value yielded by the wrapped dependency
        return await request.state.response_scoped_stack.enter_async_context(
            context_manager(*args, **kwargs)
        )

    # Ensure that the signature includes `request: Request` to ensure that FastAPI will
    # inject the request as a dependency; maintain the old signature so those depends
    # work
    request_parameter = inspect.signature(wrapper).parameters["request"]
    functools.update_wrapper(wrapper, dependency)

    if "request" not in signature.parameters:
        new_parameters = signature.parameters.copy()
        new_parameters["request"] = request_parameter
        wrapper.__signature__ = signature.replace(
            parameters=tuple(new_parameters.values())
        )

    return wrapper


class OrionAPIRoute(APIRoute):
    """
    A FastAPI APIRoute class which attaches an async stack to requests that exits before
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


def compare_open_api_schemas(base: dict, revision: dict) -> str:
    """
    Compare two open API schemas and generate descriptive markdown of the changes.

    Changes should include
    - Added routes
    - Deleted routes
    - Schema changes
    """
    report = ""
    base_routes = _get_routes_from_schema(schema=base)
    revised_routes = _get_routes_from_schema(schema=revision)

    deleted_routes = _get_deleted_routes(
        base_routes=base_routes, revised_routes=revised_routes
    )
    report += "## Deleted routes\n"
    report += _get_report_text_for_deleted_routes(deleted_routes=deleted_routes)
    report += "\n\n"
    added_routes = _get_added_routes(
        base_routes=base_routes, revised_routes=revised_routes
    )
    report += "## Added routes\n"
    report += _get_report_text_for_added_routes(
        added_routes=added_routes, revised_routes=revised_routes
    )
    report += "\n\n"

    report += "## Route changes\n"
    changed_routes = _get_route_changes(
        base_routes=base_routes, revised_routes=revised_routes
    )
    report += "\n".join(changed_routes)

    print(report)


def _get_report_text_for_deleted_routes(deleted_routes: list[str]) -> str:
    """
    Given a list of deleted routes, generate report text.
    """
    if len(deleted_routes) == 0:
        return "No routes deleted"
    deleted_route_text_list = "\n".join(deleted_routes)
    return f"The following routes have been deleted:\n {deleted_route_text_list}"


def _get_report_text_for_added_routes(
    added_routes: list[str], revised_routes: dict
) -> str:
    """
    Given a list of added routes, generate report text.

    Args:
        added_routes: a list of routes added
        revised_routes: a dictionary containing information about
            the revised routes, this will be used to populate info
            about added routes
    """
    if len(added_routes) == 0:
        return "No routes added."

    added_routes_text = "The following routes have been added:\n"
    for route in added_routes:
        added_routes_text += f"### {route}"
        description = revised_routes[route].get("description", "")
        added_routes_text += f"\nDescription: {description}"
        added_routes_text += (
            f"\nParameters:\n{_format_parameters(revised_routes[route])}"
        )

    return added_routes_text


def _format_parameters(route: dict) -> str:
    """
    Format an OpenAPI route parameter spec in readable text.
    """
    parameter_text = ""
    for param in route.get("parameters", []):
        param_name = param["name"]
        param_required = param["required"]
        param_location = param["in"]
        param_type = param["schema"]["type"]

        parameter_text += f"Name: {param_name}\n"
        parameter_text += f"Location: {param_location}\n"
        parameter_text += f"Required?: {param_required}\n"
        parameter_text += f"Type: {param_type}\n"
        parameter_text += "\n"

    # check for body params, note this only
    # checks for application/json types at the moment
    if route.get("requestBody"):
        parameter_text += f"Name: <request body>\nLocation: Body\nRequred?: True\n"
        # TODO - resolve refs here
        parameter_text += (
            f"Type: {route['requestBody']['content']['application/json']['schema']}\n"
        )
        parameter_text += "\n"
    return parameter_text


def _get_routes_from_schema(schema: dict) -> dict:
    """
    Extracts routes from a fast api schema.
    Outputs a dict of the form:

    {VERB /path/to/route: <route schema>}
    """
    routes = dict()
    for path in schema["paths"].keys():
        for path_op in schema["paths"][path].keys():
            routes[f"{path_op.upper()} - {path}"] = schema["paths"][path][path_op]
    return routes


def _get_deleted_routes(base_routes: dict, revised_routes: dict) -> list[str]:
    """
    Gets any routes that were deleted from `base_routes` in `revised_routes`.
    """
    deleted_routes = base_routes.keys() - revised_routes.keys()
    return deleted_routes


def _get_added_routes(base_routes: dict, revised_routes: dict) -> list[str]:
    """
    Gets any routes that were added to `revised_routes` not present in `base_routes`.
    """
    added_routes = revised_routes.keys() - base_routes.keys()
    return added_routes


def _get_route_changes(base_routes, revised_routes):
    # TODO - this should check for schema changes too
    changed_routes = []
    for route in revised_routes:
        if route in base_routes and base_routes[route] != revised_routes[route]:
            changed_routes.append(route)
    return changed_routes
