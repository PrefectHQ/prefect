"""
Utilities for the Prefect REST API server.
"""

import json
from collections.abc import Coroutine, Sequence
from contextlib import AsyncExitStack
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Literal, get_type_hints

import orjson
from fastapi import APIRouter, Request, Response, status
from fastapi.routing import APIRoute
from pydantic import BaseModel
from pydantic_core import to_jsonable_python
from starlette.routing import BaseRoute


def _dump_models(
    content: BaseModel | Sequence[BaseModel], mode: Literal["json", "python"]
) -> Any:
    if isinstance(content, BaseModel):
        return content.model_dump(mode=mode)
    return [model.model_dump(mode=mode) for model in content]


def model_json_response(content: BaseModel | Sequence[BaseModel]) -> Response:
    """
    Render one or more models as a JSON response.

    Free-form values stored by older servers (like parameters nested too deeply or
    containing lone surrogates) can't be rendered by `orjson` or pydantic's JSON
    mode, so this falls back to the standard library rather than failing every
    request that reads them.
    """
    try:
        body = orjson.dumps(_dump_models(content, "json"))
    except (TypeError, ValueError):
        try:
            data = _dump_models(content, "json")
        except ValueError:
            data = _dump_models(content, "python")
        body = json.dumps(
            data,
            default=partial(to_jsonable_python, timedelta_mode="float"),
            separators=(",", ":"),
        ).encode()
    return Response(content=body, media_type="application/json")


def method_paths_from_routes(routes: Sequence[BaseRoute]) -> set[str]:
    """
    Generate a set of strings describing the given routes in the format: <method> <path>

    For example, "GET /logs/"
    """
    method_paths: set[str] = set()
    for route in routes:
        effective_route_contexts = getattr(route, "effective_route_contexts", None)
        route_candidates = (
            effective_route_contexts()
            if callable(effective_route_contexts)
            else (route,)
        )

        for route_candidate in route_candidates:
            path = getattr(route_candidate, "path", None)
            methods = getattr(route_candidate, "methods", None)
            if path is None or methods is None:
                continue

            for method in methods:
                method_paths.add(f"{method} {path}")

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
            response = None
            async with AsyncExitStack() as stack:
                request.state.response_scoped_stack = stack
                response = await default_handler(request)

            if TYPE_CHECKING:
                assert response is not None
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
