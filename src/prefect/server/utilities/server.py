"""
Utilities for the Prefect REST API server.
"""

import re
from collections.abc import Coroutine, Sequence
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Any, Callable, get_type_hints

from fastapi import APIRouter, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute


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


# A JSON `\uD800`-`\uDFFF` escape, or the raw bytes of a surrogate, which
# `json.loads` decodes with `surrogatepass`
_SURROGATE_PATTERN = re.compile(rb"\\u[dD][89a-fA-F]|\xed[\xa0-\xbf]")

# Keep request nesting below pydantic-core's (255) and orjson's (256) limits
# even after response/pagination wrapper objects are added on read.
MAX_JSON_NESTING_DEPTH = 200


def _find_excessive_nesting(
    value: Any, loc: tuple[str | int, ...], max_depth: int = MAX_JSON_NESTING_DEPTH
) -> tuple[str | int, ...] | None:
    """Return the location of the first container nested deeper than `max_depth`."""
    stack: list[tuple[Any, tuple[str | int, ...], int]] = [(value, loc, 0)]
    while stack:
        current, current_loc, depth = stack.pop()
        if isinstance(current, dict):
            if depth > max_depth:
                return current_loc
            next_depth = depth + 1
            for key, item in reversed(list(current.items())):
                if isinstance(item, (dict, list)):
                    stack.append((item, (*current_loc, key), next_depth))
        elif isinstance(current, list):
            if depth > max_depth:
                return current_loc
            next_depth = depth + 1
            for index in range(len(current) - 1, -1, -1):
                item = current[index]
                if isinstance(item, (dict, list)):
                    stack.append((item, (*current_loc, index), next_depth))
    return None


def _find_unpaired_surrogate(
    value: Any, loc: tuple[str | int, ...]
) -> tuple[str | int, ...] | None:
    """Return the location of the first string that is not encodable as UTF-8."""
    stack: list[tuple[Any, tuple[str | int, ...]]] = [(value, loc)]
    while stack:
        current, current_loc = stack.pop()
        if isinstance(current, str):
            try:
                current.encode("utf-8")
            except UnicodeEncodeError:
                return current_loc
        elif isinstance(current, dict):
            for key, item in reversed(list(current.items())):
                if isinstance(item, (str, dict, list)):
                    stack.append((item, (*current_loc, key)))
                if isinstance(key, str):
                    stack.append((key, current_loc))
        elif isinstance(current, list):
            for index in range(len(current) - 1, -1, -1):
                item = current[index]
                if isinstance(item, (str, dict, list)):
                    stack.append((item, (*current_loc, index)))
    return None


async def _validate_json_body(request: Request) -> None:
    """
    Reject JSON bodies containing excessively nested containers or unpaired
    surrogates (e.g. `"\\ud800"`), which cannot be serialized cleanly on read.
    """
    if "json" not in request.headers.get("content-type", "application/json").lower():
        return
    raw_body = await request.body()
    has_surrogate_bytes = bool(_SURROGATE_PATTERN.search(raw_body))
    might_exceed_depth = (
        len(raw_body) > MAX_JSON_NESTING_DEPTH
        and (raw_body.count(b"[") + raw_body.count(b"{")) > MAX_JSON_NESTING_DEPTH
    )
    if not has_surrogate_bytes and not might_exceed_depth:
        return
    try:
        body = await request.json()
    except ValueError:
        # Leave reporting malformed JSON to FastAPI
        return
    except RecursionError:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("body",),
                    "msg": (
                        f"JSON nesting depth exceeds maximum allowed depth of "
                        f"{MAX_JSON_NESTING_DEPTH}"
                    ),
                    "input": None,
                }
            ],
            body=None,
        )

    if (
        might_exceed_depth
        and (loc := _find_excessive_nesting(body, ("body",))) is not None
    ):
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": loc,
                    "msg": (
                        f"JSON nesting depth exceeds maximum allowed depth of "
                        f"{MAX_JSON_NESTING_DEPTH}"
                    ),
                    "input": None,
                }
            ],
            body=None,
        )

    if has_surrogate_bytes:
        loc = _find_unpaired_surrogate(body, ("body",))
        if loc is not None:
            raise RequestValidationError(
                [
                    {
                        "type": "string_unicode",
                        "loc": loc,
                        "msg": "String should not contain unpaired surrogates",
                        "input": None,
                    }
                ],
                body=body,
            )


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
            if self.body_field is not None:
                await _validate_json_body(request)

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
