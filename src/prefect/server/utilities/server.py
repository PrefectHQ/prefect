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


def _find_unpaired_surrogate(
    value: Any, loc: tuple[str | int, ...]
) -> tuple[str | int, ...] | None:
    """Return the location of the first string that is not encodable as UTF-8."""
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return loc
    elif isinstance(value, dict):
        for key, item in value.items():
            if _find_unpaired_surrogate(key, loc) is not None:
                return loc
            if (found := _find_unpaired_surrogate(item, (*loc, key))) is not None:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if (found := _find_unpaired_surrogate(item, (*loc, index))) is not None:
                return found
    return None


async def _reject_unpaired_surrogates(request: Request) -> None:
    """
    Reject JSON bodies containing unpaired surrogates (e.g. `"\\ud800"`), which
    cannot be encoded as UTF-8 and so can neither be stored nor returned.
    """
    if "json" not in request.headers.get("content-type", "application/json"):
        return
    if not _SURROGATE_PATTERN.search(await request.body()):
        return
    try:
        body = await request.json()
    except ValueError:
        # Leave reporting malformed JSON to FastAPI
        return
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


async def _reject_extra_embedded_body_keys(
    request: Request, body_params: Sequence[Any]
) -> None:
    """
    Reject JSON bodies with unknown top-level keys on endpoints whose request body
    embeds more than one parameter (for example the `/filter` and `/count`
    endpoints, which embed several optional filter objects).

    FastAPI wraps multiple body parameters in a generated model that allows extra
    keys, so a misspelled top-level key such as `flow_run` for `flow_runs` is
    silently dropped and the filter it was meant to carry is ignored, which makes
    the endpoint return every row. Unknown keys one level down are already rejected
    by the individual filter models; this makes the top level behave the same way.
    """
    if len(body_params) <= 1:
        return
    if "json" not in request.headers.get("content-type", "application/json"):
        return
    try:
        body = await request.json()
    except ValueError:
        # Leave reporting malformed JSON to FastAPI
        return
    if not isinstance(body, dict):
        return
    allowed = {field.alias for field in body_params}
    errors = [
        {
            "type": "extra_forbidden",
            "loc": ("body", key),
            "msg": "Extra inputs are not permitted",
            "input": value,
        }
        for key, value in body.items()
        if key not in allowed
    ]
    if errors:
        raise RequestValidationError(errors, body=body)


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
                await _reject_unpaired_surrogates(request)
                await _reject_extra_embedded_body_keys(
                    request, self.dependant.body_params
                )

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
