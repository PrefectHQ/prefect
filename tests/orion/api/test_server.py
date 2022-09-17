from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import toml
from fastapi import APIRouter, status, testclient

from prefect.orion.api.server import (
    API_ROUTERS,
    _memoize_block_auto_registration,
    create_orion_api,
    method_paths_from_routes,
)
from prefect.settings import (
    PREFECT_MEMO_STORE_PATH,
    PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION,
    temporary_settings,
)
from prefect.testing.utilities import AsyncMock


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
        "manifest_path": "file.json",
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
        with patch("prefect.orion.api.server.hash_objects") as mock:
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
        with patch("prefect.orion.api.server.hash_objects") as mock:
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
        with patch("prefect.orion.api.server.hash_objects") as mock:
            mock.return_value = current_block_registry_hash
            await _memoize_block_auto_registration(test_func)()

        test_func.assert_not_called()

    async def test_runs_wrapped_function_when_hashing_fails(
        self, memo_store_with_accurate_key
    ):

        test_func = AsyncMock()

        with patch("prefect.orion.api.server.hash_objects") as mock:
            mock.return_value = None
            await _memoize_block_auto_registration(test_func)()

        test_func.assert_called_once()
