import inspect
from collections.abc import Callable, Generator, Iterator
from typing import Any, Optional
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.testclient import TestClient
from httpx import AsyncClient

from prefect.server.api.dependencies import (
    aget_prefect_client_version,
    docket,
    get_created_by,
    get_prefect_client_version,
    get_updated_by,
    is_ephemeral_request,
    provide_request_api_version,
)
from prefect.server.api.events import verified_page_token
from prefect.server.api.server import API_ROUTERS
from prefect.server.api.workers import WorkerLookups
from prefect.server.database import (
    aprovide_database_interface,
    provide_database_interface,
)

pytestmark = pytest.mark.clear_db


@pytest.mark.parametrize(
    "dependency", [get_prefect_client_version, aget_prefect_client_version]
)
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
    dependency: Callable[..., Any], header: str, expected: str
):
    app = FastAPI()

    @app.get("/version")
    async def get_version(
        prefect_client_version: Optional[str] = Depends(dependency),
    ):
        return prefect_client_version

    with TestClient(app) as client:
        response = client.get(
            "/version", headers={"User-Agent": header} if header is not None else {}
        )
        assert response.status_code == 200
        assert response.json() == expected


@pytest.mark.parametrize(
    "helper",
    [
        provide_request_api_version,
        get_created_by,
        get_updated_by,
        is_ephemeral_request,
        get_prefect_client_version,
        docket,
        verified_page_token,
    ],
)
def test_dependency_helpers_stay_synchronous(helper: Callable[..., Any]):
    """
    API routes depend on async variants of these helpers. Code that calls a
    helper directly still receives its result, not a coroutine.
    """
    assert not inspect.iscoroutinefunction(helper)


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


class _UnavailableDatabase:
    async def is_db_connectable(self) -> bool:
        return False


class _OverrideSelected(Exception):
    pass


@pytest.fixture
def api_app(app: FastAPI) -> Iterator[FastAPI]:
    api_app: FastAPI = app.api_app
    original_overrides = dict(api_app.dependency_overrides)
    yield api_app
    api_app.dependency_overrides.clear()
    api_app.dependency_overrides.update(original_overrides)


@pytest.fixture
def override_raises_status(api_app: FastAPI) -> Callable[[Any], None]:
    def register(dependency: Any) -> None:
        def override() -> None:
            raise HTTPException(status_code=status.HTTP_418_IM_A_TEAPOT)

        api_app.dependency_overrides[dependency] = override

    return register


async def test_ready_uses_database_override_for_original_provider(
    api_app: FastAPI, client: AsyncClient
):
    def unavailable_database() -> _UnavailableDatabase:
        return _UnavailableDatabase()

    api_app.dependency_overrides[provide_database_interface] = unavailable_database

    response = await client.get("/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"message": "Database is not available"}


async def test_ready_uses_database_override_for_async_provider(
    api_app: FastAPI, client: AsyncClient
):
    async def unavailable_database() -> _UnavailableDatabase:
        return _UnavailableDatabase()

    api_app.dependency_overrides[aprovide_database_interface] = unavailable_database

    response = await client.get("/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


async def test_override_for_async_provider_takes_precedence_over_original(
    api_app: FastAPI, client: AsyncClient
):
    def original_override() -> None:
        raise _OverrideSelected()

    async def async_override() -> _UnavailableDatabase:
        return _UnavailableDatabase()

    api_app.dependency_overrides[provide_database_interface] = original_override
    api_app.dependency_overrides[aprovide_database_interface] = async_override

    response = await client.get("/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.parametrize(
    "original,method,path",
    [
        (provide_database_interface, "GET", "/ready"),
        (provide_request_api_version, "DELETE", f"/block_schemas/{uuid4()}"),
        (get_created_by, "POST", "/flow_runs/"),
        (get_updated_by, "POST", "/deployments/"),
        (is_ephemeral_request, "POST", "/events"),
        (get_prefect_client_version, "GET", "/work_pools/my-pool"),
        (docket, "POST", "/work_pools/my-pool/get_scheduled_flow_runs"),
        (verified_page_token, "GET", "/events/filter/next?page-token=abc"),
        (WorkerLookups, "GET", "/work_pools/my-pool"),
    ],
)
async def test_routes_use_overrides_registered_for_original_dependencies(
    override_raises_status: Callable[[Any], None],
    client: AsyncClient,
    original: Callable[..., Any],
    method: str,
    path: str,
):
    override_raises_status(original)

    response = await client.request(method, path)

    assert response.status_code == status.HTTP_418_IM_A_TEAPOT


async def test_original_header_dependency_override_declares_its_own_parameters(
    api_app: FastAPI, client: AsyncClient, work_pool: Any
):
    async def client_version_from_custom_header(
        x_custom_client_version: str = Header(),
    ) -> str:
        return x_custom_client_version

    api_app.dependency_overrides[get_prefect_client_version] = (
        client_version_from_custom_header
    )

    response = await client.get(
        f"/work_pools/{work_pool.name}",
        headers={"x-custom-client-version": "3.3.7"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert (
        "default_result_storage_block_id"
        not in response.json()["storage_configuration"]
    )

    response = await client.get(f"/work_pools/{work_pool.name}")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["exception_detail"][0]["loc"] == [
        "header",
        "x-custom-client-version",
    ]


async def test_original_class_dependency_override_resolves_nested_generator(
    api_app: FastAPI, client: AsyncClient, work_pool: Any
):
    events: list[str] = []

    def request_marker(request: Request) -> object:
        events.append("marker")
        return object()

    def worker_lookups(
        first_marker: object = Depends(request_marker),
        second_marker: object = Depends(request_marker),
    ) -> Generator[WorkerLookups, None, None]:
        assert first_marker is second_marker
        events.append("enter")
        try:
            yield WorkerLookups()
        finally:
            events.append("exit")

    api_app.dependency_overrides[WorkerLookups] = worker_lookups

    response = await client.get(f"/work_pools/{work_pool.name}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == str(work_pool.id)
    assert events == ["marker", "enter", "exit"]

    events.clear()
    response = await client.get("/work_pools/does-not-exist")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert events == ["marker", "enter", "exit"]
