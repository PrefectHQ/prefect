import base64
import pathlib
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

import prefect
from prefect.server.api.server import create_app
from prefect.settings import (
    PREFECT_SERVER_API_AUTH_STRING,
    PREFECT_SERVER_CSRF_PROTECTION_ENABLED,
    PREFECT_UI_API_URL,
    PREFECT_UI_STATIC_DIRECTORY,
    temporary_settings,
)


def test_app_generates_correct_api_openapi_schema():
    """
    Test that helps detect situations in which our REST API reference docs
    fail to render properly.
    """
    schema = create_app(ephemeral=True).openapi()

    assert len(schema["paths"].keys()) > 1
    # Paths should be relative to the API base URL (PREFECT_API_URL),
    # not absolute from server root. This avoids the /api/api/ duplication
    # issue when users combine PREFECT_API_URL with documented endpoints.
    assert all([p.startswith("/") for p in schema["paths"].keys()])
    assert not any([p.startswith("/api/") for p in schema["paths"].keys()])


def _write_fake_ui_bundle(directory: pathlib.Path, marker: str) -> pathlib.Path:
    directory.mkdir(parents=True)
    (directory / "index.html").write_text(f"<html>{marker}</html>", encoding="utf-8")
    return directory


def test_app_exposes_ui_settings(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        prefect,
        "__ui_static_path__",
        _write_fake_ui_bundle(tmp_path / "v1-source", "V1 UI"),
    )
    monkeypatch.setattr(
        prefect,
        "__ui_v2_static_path__",
        _write_fake_ui_bundle(tmp_path / "v2-source", "V2 UI"),
    )

    with temporary_settings({PREFECT_UI_STATIC_DIRECTORY: str(tmp_path / "ui-static")}):
        app = create_app(ignore_cache=True)

    client = TestClient(app)
    response = client.get("/ui-settings")
    response.raise_for_status()
    assert response.json() == {
        "api_url": PREFECT_UI_API_URL.value(),
        "csrf_enabled": PREFECT_SERVER_CSRF_PROTECTION_ENABLED.value(),
        "auth": "BASIC" if PREFECT_SERVER_API_AUTH_STRING.value() else None,
        "flags": [],
        "default_ui": "v1",
        "available_uis": ["v1", "v2"],
        "v1_base_url": "/",
        "v2_base_url": "/v2",
    }


@pytest.mark.parametrize("enabled", [True, False])
def test_app_add_csrf_middleware_when_enabled(enabled: bool):
    with temporary_settings({PREFECT_SERVER_CSRF_PROTECTION_ENABLED: enabled}):
        app = create_app()
        matching = [
            middleware
            for middleware in app.user_middleware
            if "CsrfMiddleware" in str(middleware)
        ]
        assert len(matching) == (1 if enabled else 0)


class TestAuthMiddleware:
    AUTH_STRING = "admin:test"
    VALID_AUTH_HEADER = "Basic " + base64.b64encode(b"admin:test").decode()

    @pytest.fixture()
    def anonymous_client(self) -> Generator[TestClient, None, None]:
        with temporary_settings({PREFECT_SERVER_API_AUTH_STRING: self.AUTH_STRING}):
            app = create_app(ignore_cache=True)
            yield TestClient(app)

    def test_health_bypasses_auth(self, anonymous_client: TestClient):
        response = anonymous_client.get("/api/health")
        assert response.status_code == 200

    def test_ready_bypasses_auth(self, anonymous_client: TestClient):
        response = anonymous_client.get("/api/ready")
        assert response.status_code == 200

    def test_other_routes_require_auth(self, anonymous_client: TestClient):
        response = anonymous_client.get("/api/version")
        assert response.status_code == 401

    def test_valid_auth_allows_access(self, anonymous_client: TestClient):
        response = anonymous_client.get(
            "/api/version",
            headers={"Authorization": self.VALID_AUTH_HEADER},
        )
        assert response.status_code == 200

    def test_path_ending_in_health_does_not_bypass_auth(
        self, anonymous_client: TestClient
    ):
        """Regression: suffix matching allowed bypass via resource names like
        /api/variables/name/system-health"""
        response = anonymous_client.get("/api/variables/name/system-health")
        assert response.status_code == 401

    def test_path_ending_in_ready_does_not_bypass_auth(
        self, anonymous_client: TestClient
    ):
        response = anonymous_client.get("/api/variables/name/system-ready")
        assert response.status_code == 401

    def test_host_header_manipulation_does_not_bypass_auth(
        self, anonymous_client: TestClient
    ):
        """Regression: Host header like 'localhost/health?' causes
        request.url.path to evaluate to '/health' while the real route
        is still served."""
        response = anonymous_client.get(
            "/api/version",
            headers={"Host": "localhost/health?"},
        )
        assert response.status_code == 401
