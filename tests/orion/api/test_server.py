from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import APIRouter, status, testclient

from prefect.orion.api.server import (
    API_ROUTERS,
    create_orion_api,
    method_paths_from_routes,
)


async def test_validation_error_handler(client):
    bad_flow_data = {"name": "my-flow", "tags": "this should be a list not a string"}
    response = await client.post("/flows/", json=bad_flow_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["exception_message"] == "Invalid request received."
    assert response.json()["exception_detail"] == [
        {
            "loc": ["body", "tags"],
            "msg": "value is not a valid list",
            "type": "type_error.list",
        }
    ]
    assert response.json()["request_body"] == bad_flow_data


async def test_validation_error_handler(client):
    # generate deployment with invalid foreign key
    bad_deployment_data = {
        "name": "my-deployment",
        "flow_id": str(uuid4()),
        "flow_data": {"encoding": "x", "blob": "y"},
    }
    response = await client.post("/deployments/", json=bad_deployment_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "Data integrity conflict" in response.json()["detail"]


async def test_health_check_route(client):
    response = await client.get("/health")
    assert response.status_code == status.HTTP_200_OK


class TestCreateOrionAPI:

    BUILTIN_ROUTES = {
        "GET /redoc",
        "GET /health",
        "HEAD /docs",
        "GET /openapi.json",
        "GET /docs/oauth2-redirect",
        "GET /docs",
        "HEAD /openapi.json",
        "HEAD /docs/oauth2-redirect",
        "HEAD /redoc",
    }

    def test_includes_all_default_paths(self):
        app = create_orion_api()

        expected = self.BUILTIN_ROUTES.copy()

        for router in API_ROUTERS:
            expected.update(method_paths_from_routes(router.routes))

        assert method_paths_from_routes(app.router.routes) == expected

    def test_allows_router_omission_with_null_override(self):
        app = create_orion_api(router_overrides={"/logs": None})

        routes = method_paths_from_routes(app.router.routes)
        assert all("/logs" not in route for route in routes)
        client = testclient.TestClient(app)
        assert client.post("/logs").status_code == status.HTTP_404_NOT_FOUND

    def test_checks_for_router_paths_during_override(self):
        router = APIRouter(prefix="/logs")

        with pytest.raises(
            ValueError,
            match="override for '/logs' is missing paths",
        ) as exc:
            create_orion_api(router_overrides={"/logs": router})

        # These are displayed in a non-deterministic order
        assert exc.match("POST /logs/filter")
        assert exc.match("POST /logs/")

    def test_checks_for_changed_prefix_during_override(self):
        router = APIRouter(prefix="/foo")

        with pytest.raises(
            ValueError,
            match="Router override for '/logs' defines a different prefix '/foo'",
        ) as exc:
            create_orion_api(router_overrides={"/logs": router})

    def test_checks_for_new_prefix_during_override(self):
        router = APIRouter(prefix="/foo")

        with pytest.raises(
            KeyError,
            match="Router override provided for prefix that does not exist: '/foo'",
        ) as exc:
            create_orion_api(router_overrides={"/foo": router})

    def test_only_includes_missing_paths_in_override_error(self):
        router = APIRouter(prefix="/logs")

        @router.post("/")
        def foo():
            pass

        with pytest.raises(
            ValueError,
            match="override for '/logs' is missing paths.* {'POST /logs/filter'}",
        ):
            create_orion_api(router_overrides={"/logs": router})

    def test_override_uses_new_router(self):
        router = APIRouter(prefix="/logs")

        logs = MagicMock()

        @router.post("/")
        def foo():
            logs()

        logs_filter = MagicMock()
        router.post("/filter")(logs_filter)

        app = create_orion_api(router_overrides={"/logs": router})
        client = testclient.TestClient(app)
        client.post("/logs")
        logs.assert_called_once()
        client.post("/logs/filter")
        logs.assert_called_once()

    def test_override_uses_new_router(self):
        router = APIRouter(prefix="/logs")

        logs = MagicMock(return_value=1)
        logs_filter = MagicMock(return_value=1)

        @router.post("/")
        def foo():
            return logs()

        @router.post("/filter")
        def bar():
            return logs_filter()

        app = create_orion_api(router_overrides={"/logs": router})
        client = testclient.TestClient(app)
        client.post("/logs/").raise_for_status()
        logs.assert_called_once()
        client.post("/logs/filter/").raise_for_status()
        logs.assert_called_once()

    def test_override_may_include_new_routes(self):
        router = APIRouter(prefix="/logs")

        logs = MagicMock(return_value=1)
        logs_get = MagicMock(return_value=1)
        logs_filter = MagicMock(return_value=1)

        @router.post("/")
        def foo():
            return logs()

        @router.post("/filter")
        def bar():
            return logs_filter()

        @router.get("/")
        def foobar():
            return logs_get()

        app = create_orion_api(router_overrides={"/logs": router})

        client = testclient.TestClient(app)
        client.get("/logs/").raise_for_status()
        logs_get.assert_called_once()
