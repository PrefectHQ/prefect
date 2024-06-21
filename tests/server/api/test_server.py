import sqlite3
from unittest.mock import MagicMock, patch
from uuid import uuid4

import asyncpg
import pytest
import sqlalchemy as sa
import toml
from fastapi import APIRouter, status, testclient
from httpx import ASGITransport, AsyncClient

from prefect.client.constants import SERVER_API_VERSION
from prefect.server.api.server import (
    API_ROUTERS,
    SQLITE_LOCKED_MSG,
    _memoize_block_auto_registration,
    create_api_app,
    create_app,
    method_paths_from_routes,
)
from prefect.settings import (
    PREFECT_API_DATABASE_CONNECTION_URL,
    PREFECT_MEMO_STORE_PATH,
    PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION,
    temporary_settings,
)
from prefect.testing.utilities import AsyncMock


async def test_validation_error_handler_422(client):
    bad_flow_data = {"name": "my-flow", "tags": "this should be a list not a string"}
    response = await client.post("/flows/", json=bad_flow_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["exception_message"] == "Invalid request received."
    assert response.json()["exception_detail"] == [
        {
            "input": "this should be a list not a string",
            "loc": ["body", "tags"],
            "msg": "Input should be a valid list",
            "type": "list_type",
        }
    ]
    assert response.json()["request_body"] == bad_flow_data


async def test_validation_error_handler_409(client):
    # generate deployment with invalid foreign key
    bad_deployment_data = {
        "name": "my-deployment",
        "flow_id": str(uuid4()),
    }
    response = await client.post("/deployments/", json=bad_deployment_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "Data integrity conflict" in response.json()["detail"]


@pytest.mark.parametrize("ephemeral", [True, False])
@pytest.mark.parametrize("errorname", ["SQLITE_BUSY", "SQLITE_BUSY_SNAPSHOT", None])
async def test_sqlite_database_locked_handler(errorname, ephemeral):
    async def raise_busy_error():
        if errorname is None:
            orig = sqlite3.OperationalError(SQLITE_LOCKED_MSG)
        else:
            orig = sqlite3.OperationalError("db locked")
            setattr(orig, "sqlite_errorname", errorname)
        raise sa.exc.OperationalError(
            "statement",
            {"params": 1},
            orig,
            Exception,
        )

    async def raise_other_error():
        orig = sqlite3.OperationalError("db locked")
        setattr(orig, "sqlite_errorname", "FOO")
        raise sa.exc.OperationalError(
            "statement",
            {"params": 1},
            orig,
            Exception,
        )

    app = create_app(ephemeral=ephemeral, ignore_cache=True)
    app.api_app.add_api_route("/raise_busy_error", raise_busy_error)
    app.api_app.add_api_route("/raise_other_error", raise_other_error)

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="https://test",
    ) as client:
        response = await client.get("/api/raise_busy_error")
        assert response.status_code == 503

        response = await client.get("/api/raise_other_error")
        assert response.status_code == 500


@pytest.mark.parametrize(
    "exc",
    (
        sa.exc.DBAPIError("statement", {"params": 0}, ValueError("orig")),
        asyncpg.exceptions.QueryCanceledError(),
        asyncpg.exceptions.ConnectionDoesNotExistError(),
        asyncpg.exceptions.CannotConnectNowError(),
        sa.exc.InvalidRequestError(),
        sa.orm.exc.DetachedInstanceError(),
    ),
)
async def test_retryable_exception_handler(exc):
    async def raise_retryable_error():
        raise exc

    async def raise_other_error():
        raise ValueError()

    app = create_app(ephemeral=True, ignore_cache=True)
    app.api_app.add_api_route("/raise_retryable_error", raise_retryable_error)
    app.api_app.add_api_route("/raise_other_error", raise_other_error)

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="https://test",
    ) as client:
        response = await client.get("/api/raise_retryable_error")
        assert response.status_code == 503

        response = await client.get("/api/raise_other_error")
        assert response.status_code == 500


async def test_health_check_route(client):
    response = await client.get("/health")
    assert response.status_code == status.HTTP_200_OK


async def test_version_route(client):
    response = await client.get("/version")
    assert response.json() == SERVER_API_VERSION
    assert response.status_code == status.HTTP_200_OK


class TestCreateOrionAPI:
    BUILTIN_ROUTES = {
        "GET /redoc",
        "GET /health",
        "GET /version",
        "HEAD /docs",
        "GET /openapi.json",
        "GET /docs/oauth2-redirect",
        "GET /docs",
        "HEAD /openapi.json",
        "HEAD /docs/oauth2-redirect",
        "HEAD /redoc",
    }

    def test_includes_all_default_paths(self):
        app = create_api_app()

        expected = self.BUILTIN_ROUTES.copy()

        for router in API_ROUTERS:
            expected.update(method_paths_from_routes(router.routes))

        assert method_paths_from_routes(app.router.routes) == expected

    def test_allows_router_omission_with_null_override(self):
        app = create_api_app(router_overrides={"/logs": None})

        routes = method_paths_from_routes(app.router.routes)
        assert all("/logs" not in route for route in routes)
        client = testclient.TestClient(app)
        with client:
            assert client.post("/logs").status_code == status.HTTP_404_NOT_FOUND

    def test_checks_for_router_paths_during_override(self):
        router = APIRouter(prefix="/logs")

        with pytest.raises(
            ValueError,
            match="override for '/logs' is missing paths",
        ) as exc:
            create_api_app(router_overrides={"/logs": router})

        # These are displayed in a non-deterministic order
        assert exc.match("POST /logs/filter")
        assert exc.match("POST /logs/")

    def test_checks_for_changed_prefix_during_override(self):
        router = APIRouter(prefix="/foo")

        with pytest.raises(
            ValueError,
            match="Router override for '/logs' defines a different prefix '/foo'",
        ):
            create_api_app(router_overrides={"/logs": router})

    def test_checks_for_new_prefix_during_override(self):
        router = APIRouter(prefix="/foo")

        with pytest.raises(
            KeyError,
            match="Router override provided for prefix that does not exist: '/foo'",
        ):
            create_api_app(router_overrides={"/foo": router})

    def test_only_includes_missing_paths_in_override_error(self):
        router = APIRouter(prefix="/logs")

        @router.post("/")
        def foo():
            pass

        with pytest.raises(
            ValueError,
            match="override for '/logs' is missing paths.* {'POST /logs/filter'}",
        ):
            create_api_app(router_overrides={"/logs": router})

    def test_override_uses_new_router(self):
        router = APIRouter(prefix="/logs")

        logs = MagicMock()

        @router.post("/")
        def foo():
            logs()

        logs_filter = MagicMock()
        router.post("/filter")(logs_filter)

        app = create_api_app(router_overrides={"/logs": router})
        client = testclient.TestClient(app)
        client.post("/logs")
        logs.assert_called_once()
        client.post("/logs/filter")
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

        app = create_api_app(router_overrides={"/logs": router})

        client = testclient.TestClient(app)
        client.get("/logs/").raise_for_status()
        logs_get.assert_called_once()


class TestMemoizeBlockAutoRegistration:
    @pytest.fixture(autouse=True)
    def enable_memoization(self, tmp_path):
        with temporary_settings(
            {
                PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION: True,
                PREFECT_MEMO_STORE_PATH: tmp_path / "memo_store.toml",
            }
        ):
            yield

    @pytest.fixture
    def memo_store_with_mismatched_key(self):
        PREFECT_MEMO_STORE_PATH.value().write_text(
            toml.dumps({"block_auto_registration": "not-a-real-key"})
        )

    @pytest.fixture
    def current_block_registry_hash(self):
        return "abcd1234"

    @pytest.fixture
    def memo_store_with_accurate_key(self, current_block_registry_hash):
        PREFECT_MEMO_STORE_PATH.value().write_text(
            toml.dumps({"block_auto_registration": current_block_registry_hash})
        )

    async def test_runs_wrapped_function_on_missing_key(
        self, current_block_registry_hash
    ):
        assert not PREFECT_MEMO_STORE_PATH.value().exists()
        assert (
            PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION.value()
        ), "Memoization is not enabled"

        test_func = AsyncMock()

        # hashing fails randomly fails when running full test suite
        # mocking the hash stabilizes this test
        with patch("prefect.server.api.server.hash_objects") as mock:
            mock.return_value = current_block_registry_hash
            await _memoize_block_auto_registration(test_func)()

        test_func.assert_called_once()

        assert PREFECT_MEMO_STORE_PATH.value().exists(), "Memo store was not created"
        assert (
            toml.load(PREFECT_MEMO_STORE_PATH.value()).get("block_auto_registration")
            == current_block_registry_hash
        ), "Key was not added to memo store"

    async def test_runs_wrapped_function_on_mismatched_key(
        self,
        memo_store_with_mismatched_key,
        current_block_registry_hash,
    ):
        assert (
            PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION.value()
        ), "Memoization is not enabled"

        test_func = AsyncMock()

        # hashing fails randomly fails when running full test suite
        # mocking the hash stabilizes this test
        with patch("prefect.server.api.server.hash_objects") as mock:
            mock.return_value = current_block_registry_hash
            await _memoize_block_auto_registration(test_func)()

        test_func.assert_called_once()

        assert (
            toml.load(PREFECT_MEMO_STORE_PATH.value()).get("block_auto_registration")
            == current_block_registry_hash
        ), "Key was not updated in memo store"

    async def test_runs_wrapped_function_when_memoization_disabled(
        self, memo_store_with_accurate_key
    ):
        with temporary_settings(
            {
                PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION: False,
            }
        ):
            test_func = AsyncMock()

            await _memoize_block_auto_registration(test_func)()

            test_func.assert_called_once()

    async def test_skips_wrapped_function_on_matching_key(
        self, current_block_registry_hash, memo_store_with_accurate_key
    ):
        test_func = AsyncMock()

        # hashing fails randomly fails when running full test suite
        # mocking the hash stabilizes this test
        with patch("prefect.server.api.server.hash_objects") as mock:
            mock.return_value = current_block_registry_hash
            await _memoize_block_auto_registration(test_func)()

        test_func.assert_not_called()

    async def test_runs_wrapped_function_when_hashing_fails(
        self, memo_store_with_accurate_key
    ):
        test_func = AsyncMock()

        with patch("prefect.server.api.server.hash_objects") as mock:
            mock.return_value = None
            await _memoize_block_auto_registration(test_func)()

        test_func.assert_called_once()

    async def test_does_not_fail_on_read_only_filesystem(self, enable_memoization):
        try:
            PREFECT_MEMO_STORE_PATH.value().parent.chmod(744)

            test_func = AsyncMock()

            with patch("prefect.server.api.server.hash_objects") as mock:
                mock.return_value = None
                await _memoize_block_auto_registration(test_func)()

            test_func.assert_called_once()

            assert not PREFECT_MEMO_STORE_PATH.value().exists()
        finally:
            PREFECT_MEMO_STORE_PATH.value().parent.chmod(777)

    async def test_changing_database_breaks_cache(self, enable_memoization):
        test_func = AsyncMock()

        await _memoize_block_auto_registration(test_func)()

        assert test_func.call_count == 1

        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: "something else",
            }
        ):
            await _memoize_block_auto_registration(test_func)()

        assert test_func.call_count == 2
