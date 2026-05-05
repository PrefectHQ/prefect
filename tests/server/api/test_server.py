import contextlib
import logging
import pathlib
import socket
import sqlite3
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import asyncpg
import httpx
import pytest
import sqlalchemy as sa
import toml
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

import prefect
from prefect._internal.compatibility.starlette import status
from prefect.client.constants import SERVER_API_VERSION
from prefect.client.orchestration import get_client
from prefect.flows import flow
from prefect.server.api.server import (
    API_ROUTERS,
    SQLITE_LOCKED_MSG,
    UI_STATIC_REFERENCE_FILE_NAME,
    SubprocessASGIServer,
    _memoize_block_auto_registration,
    _SQLiteLockedOperationalErrorFilter,
    create_api_app,
    create_app,
    create_ui_app,
)
from prefect.server.utilities.server import method_paths_from_routes
from prefect.settings import (
    PREFECT_API_DATABASE_CONNECTION_URL,
    PREFECT_API_LOG_RETRYABLE_ERRORS,
    PREFECT_API_URL,
    PREFECT_MEMO_STORE_PATH,
    PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION,
    PREFECT_SERVER_CORS_ALLOWED_HEADERS,
    PREFECT_SERVER_CORS_ALLOWED_METHODS,
    PREFECT_SERVER_CORS_ALLOWED_ORIGINS,
    PREFECT_SERVER_DOCKET_NAME,
    PREFECT_SERVER_UI_V2_ENABLED,
    PREFECT_UI_ENABLED,
    PREFECT_UI_SERVE_BASE,
    PREFECT_UI_STATIC_DIRECTORY,
    temporary_settings,
)


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

    with temporary_settings(
        {PREFECT_SERVER_DOCKET_NAME: f"test-docket-{uuid4().hex[:8]}"}
    ):
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


def _log_record_for_sqlite_error(orig_exc, logger_name: str = "uvicorn.error"):
    try:
        raise sa.exc.OperationalError("statement", {"params": 1}, orig_exc, None)
    except sa.exc.OperationalError:
        exc_info = sys.exc_info()
    return logging.LogRecord(
        name=logger_name,
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="msg",
        args=(),
        exc_info=exc_info,
    )


def test_sqlite_locked_log_filter_suppresses_when_disabled():
    filter_ = _SQLiteLockedOperationalErrorFilter()
    orig_exc = sqlite3.OperationalError(SQLITE_LOCKED_MSG)
    record = _log_record_for_sqlite_error(orig_exc)

    with temporary_settings({PREFECT_API_LOG_RETRYABLE_ERRORS: False}):
        assert filter_.filter(record) is False


def test_sqlite_locked_log_filter_allows_when_enabled():
    filter_ = _SQLiteLockedOperationalErrorFilter()
    orig_exc = sqlite3.OperationalError("db locked")
    setattr(orig_exc, "sqlite_errorname", "SQLITE_BUSY")
    record = _log_record_for_sqlite_error(orig_exc)

    with temporary_settings({PREFECT_API_LOG_RETRYABLE_ERRORS: True}):
        assert filter_.filter(record) is True


def test_sqlite_locked_log_filter_ignores_non_retryable_sqlite_errors():
    filter_ = _SQLiteLockedOperationalErrorFilter()
    orig_exc = sqlite3.OperationalError("other error")
    setattr(orig_exc, "sqlite_errorname", "FOO")
    record = _log_record_for_sqlite_error(orig_exc)

    with temporary_settings({PREFECT_API_LOG_RETRYABLE_ERRORS: False}):
        assert filter_.filter(record) is True


def test_sqlite_locked_log_filter_ignores_non_operational_errors():
    filter_ = _SQLiteLockedOperationalErrorFilter()
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="uvicorn.error",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="msg",
        args=(),
        exc_info=exc_info,
    )

    with temporary_settings({PREFECT_API_LOG_RETRYABLE_ERRORS: False}):
        assert filter_.filter(record) is True


def test_sqlite_locked_log_filter_works_for_docket_worker_logger():
    """Test that the filter also suppresses SQLite lock errors from docket.worker logger.

    This is important because docket background tasks (like mark_deployments_ready)
    can hit SQLite locking issues and log errors through the docket.worker logger.
    See: https://github.com/PrefectHQ/prefect/issues/19771
    """
    filter_ = _SQLiteLockedOperationalErrorFilter()
    orig_exc = sqlite3.OperationalError(SQLITE_LOCKED_MSG)
    record = _log_record_for_sqlite_error(orig_exc, logger_name="docket.worker")

    with temporary_settings({PREFECT_API_LOG_RETRYABLE_ERRORS: False}):
        assert filter_.filter(record) is False

    with temporary_settings({PREFECT_API_LOG_RETRYABLE_ERRORS: True}):
        assert filter_.filter(record) is True


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

    with temporary_settings(
        {PREFECT_SERVER_DOCKET_NAME: f"test-docket-{uuid4().hex[:8]}"}
    ):
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


def _write_fake_ui_bundle(directory: pathlib.Path, marker: str) -> pathlib.Path:
    directory.mkdir(parents=True)
    (directory / "index.html").write_text(
        f"<html><body>{marker} /PREFECT_UI_SERVE_BASE_REPLACE_PLACEHOLDER</body></html>",
        encoding="utf-8",
    )
    return directory


def test_create_ui_app_mounts_dual_bundles_and_exposes_ui_settings(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
):
    v1_source = _write_fake_ui_bundle(tmp_path / "v1-source", "V1 UI")
    v2_source = _write_fake_ui_bundle(tmp_path / "v2-source", "V2 UI")
    monkeypatch.setattr(prefect, "__ui_static_path__", v1_source)
    monkeypatch.setattr(prefect, "__ui_v2_static_path__", v2_source)

    static_root = tmp_path / "ui-static"
    with temporary_settings(
        {
            PREFECT_UI_ENABLED: True,
            PREFECT_UI_STATIC_DIRECTORY: str(static_root),
        }
    ):
        ui_app = create_ui_app(ephemeral=False)

    client = TestClient(ui_app)

    v1_response = client.get("/dashboard")
    assert v1_response.status_code == 200
    assert "V1 UI" in v1_response.text

    client.cookies.set("prefect_ui_version", "v2")
    v2_response = client.get("/v2/dashboard")
    assert v2_response.status_code == 200
    assert "V2 UI" in v2_response.text
    assert "/v2" in v2_response.text

    settings_response = client.get("/ui-settings")
    settings_response.raise_for_status()
    assert settings_response.json()["default_ui"] == "v1"
    assert settings_response.json()["available_uis"] == ["v1", "v2"]
    assert settings_response.json()["v1_base_url"] == "/"
    assert settings_response.json()["v2_base_url"] == "/v2"

    assert (static_root / "v1" / "index.html").exists()
    assert (static_root / "v2" / "index.html").exists()


@pytest.mark.parametrize(
    ("serve_base", "expected_v1_base", "expected_v2_base"),
    [
        ("/v2", "/", "/v2"),
        ("/prefect/v2", "/prefect", "/prefect/v2"),
    ],
)
def test_create_ui_app_preserves_existing_v2_serve_base(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    serve_base: str,
    expected_v1_base: str,
    expected_v2_base: str,
):
    v1_source = _write_fake_ui_bundle(tmp_path / "v1-source", "V1 UI")
    v2_source = _write_fake_ui_bundle(tmp_path / "v2-source", "V2 UI")
    monkeypatch.setattr(prefect, "__ui_static_path__", v1_source)
    monkeypatch.setattr(prefect, "__ui_v2_static_path__", v2_source)

    with temporary_settings(
        {
            PREFECT_UI_ENABLED: True,
            PREFECT_UI_SERVE_BASE: serve_base,
            PREFECT_UI_STATIC_DIRECTORY: str(tmp_path / "ui-static"),
        }
    ):
        ui_app = create_ui_app(ephemeral=False)

    client = TestClient(ui_app)

    v1_path = (
        "/dashboard" if expected_v1_base == "/" else f"{expected_v1_base}/dashboard"
    )
    v2_path = f"{expected_v2_base}/dashboard"
    settings_path = (
        "/ui-settings" if expected_v1_base == "/" else f"{expected_v1_base}/ui-settings"
    )

    v1_response = client.get(v1_path)
    assert v1_response.status_code == 200
    assert "V1 UI" in v1_response.text

    v2_response = client.get(v2_path)
    assert v2_response.status_code == 200
    assert "V2 UI" in v2_response.text

    settings_response = client.get(settings_path)
    settings_response.raise_for_status()
    assert settings_response.json()["v1_base_url"] == expected_v1_base
    assert settings_response.json()["v2_base_url"] == expected_v2_base


@pytest.mark.parametrize(
    ("serve_base", "request_path", "cookie_value", "expected_location"),
    [
        ("/", "/", "v2", "/v2"),
        ("/prefect", "/prefect", "v2", "/prefect/v2"),
        ("/v2", "/", "v2", "/v2"),
        ("/prefect/v2", "/prefect", "v2", "/prefect/v2"),
    ],
)
def test_create_ui_app_redirects_neutral_entrypoints_to_preferred_ui(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    serve_base: str,
    request_path: str,
    cookie_value: str,
    expected_location: str,
):
    v1_source = _write_fake_ui_bundle(tmp_path / "v1-source", "V1 UI")
    v2_source = _write_fake_ui_bundle(tmp_path / "v2-source", "V2 UI")
    monkeypatch.setattr(prefect, "__ui_static_path__", v1_source)
    monkeypatch.setattr(prefect, "__ui_v2_static_path__", v2_source)

    with temporary_settings(
        {
            PREFECT_UI_ENABLED: True,
            PREFECT_UI_SERVE_BASE: serve_base,
            PREFECT_UI_STATIC_DIRECTORY: str(tmp_path / "ui-static"),
        }
    ):
        ui_app = create_ui_app(ephemeral=False)

    client = TestClient(ui_app)
    client.cookies.set("prefect_ui_version", cookie_value)
    response = client.get(
        request_path,
        headers={"accept": "text/html"},
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"].endswith(expected_location)


def test_create_ui_app_preserves_root_path_in_redirects(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
):
    v1_source = _write_fake_ui_bundle(tmp_path / "v1-source", "V1 UI")
    v2_source = _write_fake_ui_bundle(tmp_path / "v2-source", "V2 UI")
    monkeypatch.setattr(prefect, "__ui_static_path__", v1_source)
    monkeypatch.setattr(prefect, "__ui_v2_static_path__", v2_source)

    with temporary_settings(
        {
            PREFECT_UI_ENABLED: True,
            PREFECT_UI_SERVE_BASE: "/prefect",
            PREFECT_UI_STATIC_DIRECTORY: str(tmp_path / "ui-static"),
        }
    ):
        ui_app = create_ui_app(ephemeral=False)

    client = TestClient(ui_app, root_path="/proxy")
    client.cookies.set("prefect_ui_version", "v2")
    response = client.get(
        "/proxy/prefect",
        headers={"accept": "text/html"},
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"].endswith("/proxy/prefect/v2")


@pytest.mark.parametrize(
    ("serve_base", "request_path"),
    [
        ("/", "/v2/dashboard"),
        ("/prefect", "/prefect/v2/dashboard"),
        ("/v2", "/v2/dashboard"),
        ("/prefect/v2", "/prefect/v2/dashboard"),
    ],
)
def test_create_ui_app_allows_explicit_v2_requests_without_saved_preference(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    serve_base: str,
    request_path: str,
):
    v1_source = _write_fake_ui_bundle(tmp_path / "v1-source", "V1 UI")
    v2_source = _write_fake_ui_bundle(tmp_path / "v2-source", "V2 UI")
    monkeypatch.setattr(prefect, "__ui_static_path__", v1_source)
    monkeypatch.setattr(prefect, "__ui_v2_static_path__", v2_source)

    with temporary_settings(
        {
            PREFECT_UI_ENABLED: True,
            PREFECT_UI_SERVE_BASE: serve_base,
            PREFECT_UI_STATIC_DIRECTORY: str(tmp_path / "ui-static"),
        }
    ):
        ui_app = create_ui_app(ephemeral=False)

    client = TestClient(ui_app)
    response = client.get(
        request_path,
        headers={"accept": "text/html"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "location" not in response.headers
    assert "V2 UI" in response.text


@pytest.mark.parametrize(
    ("serve_base", "request_path", "expected_location"),
    [
        ("/", "/", "/v2"),
        ("/prefect", "/prefect", "/prefect/v2"),
        ("/v2", "/", "/v2"),
        ("/prefect/v2", "/prefect", "/prefect/v2"),
    ],
)
def test_create_ui_app_uses_default_ui_for_neutral_entrypoints_without_saved_preference(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    serve_base: str,
    request_path: str,
    expected_location: str,
):
    v1_source = _write_fake_ui_bundle(tmp_path / "v1-source", "V1 UI")
    v2_source = _write_fake_ui_bundle(tmp_path / "v2-source", "V2 UI")
    monkeypatch.setattr(prefect, "__ui_static_path__", v1_source)
    monkeypatch.setattr(prefect, "__ui_v2_static_path__", v2_source)

    with temporary_settings(
        {
            PREFECT_UI_ENABLED: True,
            PREFECT_SERVER_UI_V2_ENABLED: True,
            PREFECT_UI_SERVE_BASE: serve_base,
            PREFECT_UI_STATIC_DIRECTORY: str(tmp_path / "ui-static"),
        }
    ):
        ui_app = create_ui_app(ephemeral=False)

    client = TestClient(ui_app)
    response = client.get(
        request_path,
        headers={"accept": "text/html"},
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"].endswith(expected_location)


@pytest.mark.parametrize(
    ("serve_base", "request_path"),
    [
        ("/", "/dashboard"),
        ("/", "/work-queues"),
        ("/prefect", "/prefect/dashboard"),
        ("/prefect", "/prefect/work-queues"),
    ],
)
def test_create_ui_app_keeps_v1_deep_links_on_v1_for_v2_cookie_preference(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    serve_base: str,
    request_path: str,
):
    v1_source = _write_fake_ui_bundle(tmp_path / "v1-source", "V1 UI")
    v2_source = _write_fake_ui_bundle(tmp_path / "v2-source", "V2 UI")
    monkeypatch.setattr(prefect, "__ui_static_path__", v1_source)
    monkeypatch.setattr(prefect, "__ui_v2_static_path__", v2_source)

    with temporary_settings(
        {
            PREFECT_UI_ENABLED: True,
            PREFECT_UI_SERVE_BASE: serve_base,
            PREFECT_UI_STATIC_DIRECTORY: str(tmp_path / "ui-static"),
        }
    ):
        ui_app = create_ui_app(ephemeral=False)

    client = TestClient(ui_app)
    client.cookies.set("prefect_ui_version", "v2")
    response = client.get(
        request_path,
        headers={"accept": "text/html"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "location" not in response.headers
    assert "V1 UI" in response.text


@pytest.mark.parametrize(
    ("serve_base", "request_path"),
    [
        ("/", "/dashboard"),
        ("/", "/work-queues"),
        ("/prefect", "/prefect/dashboard"),
        ("/prefect", "/prefect/work-queues"),
    ],
)
def test_create_ui_app_keeps_v1_deep_links_on_v1_for_default_v2_preference(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    serve_base: str,
    request_path: str,
):
    v1_source = _write_fake_ui_bundle(tmp_path / "v1-source", "V1 UI")
    v2_source = _write_fake_ui_bundle(tmp_path / "v2-source", "V2 UI")
    monkeypatch.setattr(prefect, "__ui_static_path__", v1_source)
    monkeypatch.setattr(prefect, "__ui_v2_static_path__", v2_source)

    with temporary_settings(
        {
            PREFECT_UI_ENABLED: True,
            PREFECT_SERVER_UI_V2_ENABLED: True,
            PREFECT_UI_SERVE_BASE: serve_base,
            PREFECT_UI_STATIC_DIRECTORY: str(tmp_path / "ui-static"),
        }
    ):
        ui_app = create_ui_app(ephemeral=False)

    client = TestClient(ui_app)
    response = client.get(
        request_path,
        headers={"accept": "text/html"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "location" not in response.headers
    assert "V1 UI" in response.text


@pytest.mark.parametrize(
    ("request_path", "cookie_value"),
    [
        ("/login?redirect=/flow-runs/123", "v2"),
        ("/v2/login?redirectTo=/runs/flow-run/123", "v1"),
    ],
)
def test_create_ui_app_keeps_login_on_requested_ui_when_preferences_differ(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    request_path: str,
    cookie_value: str,
):
    v1_source = _write_fake_ui_bundle(tmp_path / "v1-source", "V1 UI")
    v2_source = _write_fake_ui_bundle(tmp_path / "v2-source", "V2 UI")
    monkeypatch.setattr(prefect, "__ui_static_path__", v1_source)
    monkeypatch.setattr(prefect, "__ui_v2_static_path__", v2_source)

    with temporary_settings(
        {
            PREFECT_UI_ENABLED: True,
            PREFECT_UI_STATIC_DIRECTORY: str(tmp_path / "ui-static"),
        }
    ):
        ui_app = create_ui_app(ephemeral=False)

    client = TestClient(ui_app)
    client.cookies.set("prefect_ui_version", cookie_value)
    response = client.get(
        request_path,
        headers={"accept": "text/html"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "location" not in response.headers


def test_create_ui_app_does_not_redirect_non_html_requests(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
):
    v1_source = _write_fake_ui_bundle(tmp_path / "v1-source", "V1 UI")
    v2_source = _write_fake_ui_bundle(tmp_path / "v2-source", "V2 UI")
    monkeypatch.setattr(prefect, "__ui_static_path__", v1_source)
    monkeypatch.setattr(prefect, "__ui_v2_static_path__", v2_source)

    with temporary_settings(
        {
            PREFECT_UI_ENABLED: True,
            PREFECT_UI_STATIC_DIRECTORY: str(tmp_path / "ui-static"),
        }
    ):
        ui_app = create_ui_app(ephemeral=False)

    client = TestClient(ui_app)
    client.cookies.set("prefect_ui_version", "v2")
    response = client.get("/dashboard", headers={"accept": "application/json"})

    assert response.status_code == 200
    assert "location" not in response.headers
    assert "V1 UI" in response.text


def test_create_ui_app_uses_legacy_static_directory_layout_for_v1(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
):
    static_dir = tmp_path / "ui-static"
    v1_source = _write_fake_ui_bundle(tmp_path / "v1-source", "Unused V1 Source")
    v2_source = _write_fake_ui_bundle(tmp_path / "v2-source", "V2 UI")
    _write_fake_ui_bundle(static_dir, "V1 Legacy UI")
    (static_dir / UI_STATIC_REFERENCE_FILE_NAME).write_text(
        f"v1:{prefect.__version__}:/",
        encoding="utf-8",
    )

    monkeypatch.setattr(prefect, "__ui_static_path__", v1_source)
    monkeypatch.setattr(prefect, "__ui_v2_static_path__", v2_source)

    with temporary_settings(
        {
            PREFECT_UI_ENABLED: True,
            PREFECT_UI_STATIC_DIRECTORY: str(static_dir),
        }
    ):
        ui_app = create_ui_app(ephemeral=False)

    client = TestClient(ui_app)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "V1 Legacy UI" in response.text

    v2_response = client.get("/v2/dashboard")
    assert v2_response.status_code == 200
    assert "V2 UI" in v2_response.text

    route_names = [r.name for r in ui_app.routes if hasattr(r, "name")]
    assert "ui_v1" in route_names
    assert "ui_v2" in route_names
    assert not (static_dir / "v1").exists()
    assert (static_dir / "v2" / "index.html").exists()


def test_create_ui_app_does_not_reuse_unmarked_static_directory_root(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
):
    static_dir = tmp_path / "ui-static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text(
        "<html><body>Unrelated directory</body></html>",
        encoding="utf-8",
    )
    (static_dir / "keep.txt").write_text("preserve me", encoding="utf-8")

    v1_source = _write_fake_ui_bundle(tmp_path / "v1-source", "V1 UI")
    v2_source = _write_fake_ui_bundle(tmp_path / "v2-source", "V2 UI")
    monkeypatch.setattr(prefect, "__ui_static_path__", v1_source)
    monkeypatch.setattr(prefect, "__ui_v2_static_path__", v2_source)

    with temporary_settings(
        {
            PREFECT_UI_ENABLED: True,
            PREFECT_UI_STATIC_DIRECTORY: str(static_dir),
        }
    ):
        ui_app = create_ui_app(ephemeral=False)

    client = TestClient(ui_app)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "V1 UI" in response.text

    assert (static_dir / "index.html").read_text(encoding="utf-8") == (
        "<html><body>Unrelated directory</body></html>"
    )
    assert (static_dir / "keep.txt").read_text(encoding="utf-8") == "preserve me"
    assert (static_dir / "v1" / "index.html").exists()
    assert (static_dir / "v2" / "index.html").exists()


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
        assert PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION.value(), (
            "Memoization is not enabled"
        )

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
        assert PREFECT_MEMOIZE_BLOCK_AUTO_REGISTRATION.value(), (
            "Memoization is not enabled"
        )

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


def test_create_ui_app_handles_permission_error_on_static_files(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Regression test for https://github.com/PrefectHQ/prefect/issues/19317

    When running in a read-only container, copying UI static files raises
    PermissionError. create_ui_app should catch this, log an error, and
    return the app without the static file mount.
    """

    static_dir = str(tmp_path / "ui-static")

    v1_source = _write_fake_ui_bundle(tmp_path / "v1-source", "V1 UI")
    v2_source = _write_fake_ui_bundle(tmp_path / "v2-source", "V2 UI")
    monkeypatch.setattr(prefect, "__ui_static_path__", v1_source)
    monkeypatch.setattr(prefect, "__ui_v2_static_path__", v2_source)

    with temporary_settings(
        {
            PREFECT_UI_ENABLED: True,
            PREFECT_UI_STATIC_DIRECTORY: static_dir,
        }
    ):
        with (
            patch(
                "prefect.server.api.server.copy_directory",
                side_effect=PermissionError(
                    "[Errno 30] Read-only file system: " + static_dir
                ),
            ),
            patch("prefect.server.api.server.logger") as mock_logger,
        ):
            ui_app = create_ui_app(ephemeral=False)

    assert mock_logger.error.call_count >= 1
    assert all(
        "Failed to create" in call.args[0] for call in mock_logger.error.call_args_list
    )
    # The app should not have the static file mounts
    route_names = [r.name for r in ui_app.routes if hasattr(r, "name")]
    assert "ui_v1" not in route_names
    assert "ui_v2" not in route_names
