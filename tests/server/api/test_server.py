import contextlib
import socket
import sqlite3
from unittest.mock import MagicMock, patch
from uuid import uuid4

import asyncpg
import httpx
import pytest
import sqlalchemy as sa
import toml
from fastapi import status
from httpx import ASGITransport, AsyncClient

from prefect.client.constants import SERVER_API_VERSION
from prefect.client.orchestration import get_client
from prefect.flows import flow
from prefect.server.api.server import (
    API_ROUTERS,
    SQLITE_LOCKED_MSG,
    SubprocessASGIServer,
    _memoize_block_auto_registration,
    create_api_app,
    create_app,
)
from prefect.server.utilities.server import method_paths_from_routes
from prefect.settings import (
    PREFECT_API_DATABASE_CONNECTION_URL,
    PREFECT_API_URL,
    PREFECT_MEMO_STORE_PATH,
    PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION,
    PREFECT_SERVER_CORS_ALLOWED_HEADERS,
    PREFECT_SERVER_CORS_ALLOWED_METHODS,
    PREFECT_SERVER_CORS_ALLOWED_ORIGINS,
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


@pytest.mark.skip(reason="This test is flaky and needs to be fixed")
async def test_cors_middleware_settings():
    with SubprocessASGIServer() as server:
        health_response = httpx.options(
            f"{server.api_url}/health",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert health_response.status_code == 200
        assert health_response.headers["Access-Control-Allow-Origin"] == "*"
        assert (
            health_response.headers["Access-Control-Allow-Methods"]
            == "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT"
        )
        assert "Access-Control-Allow-Headers" not in health_response.headers

    with temporary_settings(
        {
            PREFECT_SERVER_CORS_ALLOWED_ORIGINS: "http://example.com",
            PREFECT_SERVER_CORS_ALLOWED_METHODS: "GET,POST",
            PREFECT_SERVER_CORS_ALLOWED_HEADERS: "x-tra-header",
        }
    ):
        with SubprocessASGIServer() as server:
            health_response = httpx.options(
                f"{server.api_url}/health",
                headers={
                    "Origin": "http://example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert health_response.status_code == 200
            assert (
                health_response.headers["Access-Control-Allow-Origin"]
                == "http://example.com"
            )
            assert (
                health_response.headers["Access-Control-Allow-Methods"] == "GET, POST"
            )
            assert (
                "x-tra-header"
                in health_response.headers["Access-Control-Allow-Headers"]
            )


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


class TestSubprocessASGIServer:
    def test_singleton_on_port(self):
        server_8001 = SubprocessASGIServer(port=8001)
        assert server_8001 is SubprocessASGIServer(port=8001)

        server_random = SubprocessASGIServer()
        assert server_random is SubprocessASGIServer()

        assert server_8001 is not server_random

    def test_find_available_port_returns_available_port(self):
        server = SubprocessASGIServer()
        port = server.find_available_port()
        assert server.is_port_available(port)
        assert 8000 <= port < 9000

    def test_is_port_available_returns_true_for_available_port(self):
        server = SubprocessASGIServer()
        port = server.find_available_port()
        assert server.is_port_available(port)

    def test_is_port_available_returns_false_for_unavailable_port(self):
        server = SubprocessASGIServer()
        with contextlib.closing(
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ) as sock:
            sock.bind(("127.0.0.1", 12345))
            assert not server.is_port_available(12345)

    def test_start_is_idempotent(self, respx_mock, monkeypatch):
        popen_mock = MagicMock()
        monkeypatch.setattr("prefect.server.api.server.subprocess.Popen", popen_mock)
        respx_mock.get("http://127.0.0.1:8000/api/health").respond(status_code=200)
        server = SubprocessASGIServer(port=8000)
        server.start()
        server.start()

        assert popen_mock.call_count == 1

    def test_address_returns_correct_address(self):
        server = SubprocessASGIServer(port=8000)
        assert server.address == "http://127.0.0.1:8000"

    def test_address_returns_correct_api_url(self):
        server = SubprocessASGIServer(port=8000)
        assert server.api_url == "http://127.0.0.1:8000/api"

    @pytest.mark.skip(reason="This test is flaky and needs to be fixed")
    def test_start_and_stop_server(self):
        server = SubprocessASGIServer()
        server.start()
        health_response = httpx.get(f"{server.address}/api/health")
        assert health_response.status_code == 200

        server.stop()
        with pytest.raises(httpx.RequestError):
            httpx.get(f"{server.api_url}/health")

    @pytest.mark.skip(reason="This test is flaky and needs to be fixed")
    def test_run_as_context_manager(self):
        with SubprocessASGIServer() as server:
            health_response = httpx.get(f"{server.api_url}/health")
            assert health_response.status_code == 200

        with pytest.raises(httpx.RequestError):
            httpx.get(f"{server.api_url}/health")

    @pytest.mark.skip(reason="This test is flaky and needs to be fixed")
    def test_run_a_flow_against_subprocess_server(self):
        @flow
        def f():
            return 42

        server = SubprocessASGIServer()
        server.start()

        with temporary_settings({PREFECT_API_URL: server.api_url}):
            assert f() == 42

            client = get_client(sync_client=True)
            assert len(client.read_flow_runs()) == 1

        server.stop()

    def test_run_with_temp_db(self):
        """
        This test ensures that the format of the database connection URL used for the default
        test profile does not retain state between subprocess server runs.
        """

        @flow
        def f():
            return 42

        with temporary_settings(
            {PREFECT_API_DATABASE_CONNECTION_URL: "sqlite+aiosqlite:///:memory:"}
        ):
            SubprocessASGIServer._instances = {}
            server = SubprocessASGIServer()
            server.start(timeout=30)

            with temporary_settings({PREFECT_API_URL: server.api_url}):
                assert f() == 42

                client = get_client(sync_client=True)
                assert len(client.read_flow_runs()) == 1

            server.stop()

            # do it again to ensure the db is recreated

            server = SubprocessASGIServer()
            server.start(timeout=30)

            with temporary_settings({PREFECT_API_URL: server.api_url}):
                assert f() == 42

                client = get_client(sync_client=True)
                assert len(client.read_flow_runs()) == 1

            server.stop()
