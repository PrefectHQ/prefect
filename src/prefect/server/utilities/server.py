"""
Utilities for the Prefect REST API server.
"""

import re
from collections.abc import Coroutine, Sequence
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Any, Callable, get_type_hints

from fastapi import APIRouter, Request, Response, status
from fastapi import params as fastapi_params
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict
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


_STRICT_TOP_LEVEL_BODY_SUFFIXES = ("/filter", "/count", "/paginate")


def _is_strict_top_level_body_path(path: str) -> bool:
    trimmed = path.rstrip("/")
    return trimmed.endswith(_STRICT_TOP_LEVEL_BODY_SUFFIXES) or "/count-by/" in trimmed


def configure_strict_body_field(route_like: Any) -> frozenset[str] | None:
    """
    Mark generated multi-parameter body models on `/filter`, `/count`, and `/paginate`
    routes with `extra="forbid"` (refreshing FastAPI's cached `TypeAdapter` so OpenAPI
    emits `additionalProperties: false`) and return the allowed top-level JSON keys.
    """
    body_field = getattr(route_like, "body_field", None)
    path = getattr(route_like, "path", None)
    if (
        body_field is None
        or not isinstance(path, str)
        or not getattr(route_like, "_embed_body_fields", False)
        or isinstance(body_field.field_info, (fastapi_params.Form, fastapi_params.File))
        or not _is_strict_top_level_body_path(path)
    ):
        return None

    body_model = getattr(body_field.field_info, "annotation", None)
    if not (isinstance(body_model, type) and issubclass(body_model, BaseModel)):
        return None

    body_model.model_config = ConfigDict(
        **dict(body_model.model_config), extra="forbid"
    )
    body_model.model_rebuild(force=True)
    if hasattr(body_field, "__post_init__"):
        body_field.__post_init__()

    return frozenset(
        (field_info.alias or name)
        for name, field_info in body_model.model_fields.items()
    ) | frozenset(body_model.model_fields.keys())


def enforce_strict_body_fields_on_routes(routes: Sequence[BaseRoute]) -> None:
    """
    Ensure effective route contexts created by `app.include_router(...)` also rebuild
    their synthesized `Body_*` models with `extra="forbid"` for OpenAPI generation.
    """
    for route in routes:
        effective_route_contexts = getattr(route, "effective_route_contexts", None)
        candidates = (
            effective_route_contexts()
            if callable(effective_route_contexts)
            else (route,)
        )
        for candidate in candidates:
            configure_strict_body_field(candidate)


async def _reject_unknown_top_level_body_keys(
    request: Request, allowed_keys: frozenset[str]
) -> None:
    """
    Reject unknown top-level JSON object keys on `/filter`, `/count`, and `/paginate`
    endpoints so misspelled filter or pagination keys return 422 (`extra_forbidden`)
    instead of being silently dropped by FastAPI's parameter-by-parameter extraction.
    """
    body_bytes = await request.body()
    if not body_bytes:
        return
    if "json" not in request.headers.get("content-type", "application/json").lower():
        return
    try:
        body = await request.json()
    except ValueError:
        return
    if not isinstance(body, dict):
        return

    extra_errors = [
        {
            "type": "extra_forbidden",
            "loc": ("body", key),
            "msg": "Extra inputs are not permitted",
            "input": value,
        }
        for key, value in body.items()
        if key not in allowed_keys
    ]
    if extra_errors:
        raise RequestValidationError(extra_errors, body=body)


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

    _allowed_top_level_body_keys: frozenset[str] | None = None

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        if self._allowed_top_level_body_keys is None:
            self._allowed_top_level_body_keys = configure_strict_body_field(self)
        default_handler = super().get_route_handler()
        allowed_keys = self._allowed_top_level_body_keys

        async def handle_response_scoped_depends(request: Request) -> Response:
            # Create a new stack scoped to exit before the response is returned
            if self.body_field is not None:
                await _reject_unpaired_surrogates(request)
                if allowed_keys is not None:
                    await _reject_unknown_top_level_body_keys(request, allowed_keys)

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
