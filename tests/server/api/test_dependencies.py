import inspect
from collections.abc import Callable, Iterator
from typing import Any, Optional

import pytest
from fastapi import Depends, FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.testclient import TestClient

from prefect.server.api.dependencies import get_prefect_client_version
from prefect.server.api.server import API_ROUTERS
from prefect.server.database import aprovide_database_interface

pytestmark = pytest.mark.clear_db


@pytest.mark.parametrize(
    "header,expected",
    [
        ("prefect/2.19.6 (API 0.8.4)", "2.19.6"),
        ("prefect/3.0.1 (API 2.19.3)", "3.0.1"),
        ("prefect/3.0.3+20.g6a5cc73fb6 (API 0.8.4)", "3.0.3+20.g6a5cc73fb6"),
        ("prefect/3.0.3rc3 (API unknown)", "3.0.3rc3"),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            None,
        ),
        ("random", None),
        ("", None),
        (None, None),
    ],
)
def test_get_prefect_client_version_correctly_extracts_from_header(
    header: str, expected: str
):
    app = FastAPI()

    @app.get("/version")
    async def get_version(
        prefect_client_version: Optional[str] = Depends(get_prefect_client_version),
    ):
        return prefect_client_version

    with TestClient(app) as client:
        response = client.get(
            "/version", headers={"User-Agent": header} if header is not None else {}
        )
        assert response.status_code == 200
        assert response.json() == expected


def _dependency_calls(dependant: Dependant) -> Iterator[Callable[..., Any]]:
    for dependency in dependant.dependencies:
        if dependency.call is not None:
            yield dependency.call
        yield from _dependency_calls(dependency)


def _resolves_on_event_loop(call: Callable[..., Any]) -> bool:
    if inspect.isclass(call):
        return False
    return any(
        inspect.iscoroutinefunction(function) or inspect.isasyncgenfunction(function)
        for function in (call, getattr(call, "__call__", None))
    )


def test_api_route_dependencies_resolve_on_the_event_loop():
    """
    FastAPI resolves a sync dependency in its thread pool, which costs a thread
    handoff on every request that uses it.
    """
    dependencies = {
        (route.path, call)
        for router in API_ROUTERS
        for route in router.routes
        if isinstance(route, (APIRoute, APIWebSocketRoute))
        for call in _dependency_calls(route.dependant)
    }
    assert aprovide_database_interface in {call for _, call in dependencies}

    sync_dependencies = sorted(
        f"{path}: {getattr(call, '__qualname__', repr(call))}"
        for path, call in dependencies
        if not _resolves_on_event_loop(call)
    )
    assert sync_dependencies == []
