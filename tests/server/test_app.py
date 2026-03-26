import base64
import json
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from prefect.server.api.server import create_app
from prefect.settings import (
    PREFECT_SERVER_API_AUTH_STRING,
    PREFECT_SERVER_CSRF_PROTECTION_ENABLED,
    PREFECT_UI_API_URL,
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


def test_app_exposes_ui_settings():
    app = create_app()
    client = TestClient(app)
    response = client.get("/ui-settings")
    response.raise_for_status()
    assert response.json() == {
        "api_url": PREFECT_UI_API_URL.value(),
        "csrf_enabled": PREFECT_SERVER_CSRF_PROTECTION_ENABLED.value(),
        "auth": "BASIC" if PREFECT_SERVER_API_AUTH_STRING.value() else None,
        "flags": [],
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


class TestContentTypeDefaultMiddleware:
    """Regression tests for GitHub issue #21301: older clients that send
    POST requests without a Content-Type header should not receive a 422."""

    @pytest.fixture()
    def client(self) -> Generator[TestClient, None, None]:
        app = create_app(ignore_cache=True)
        yield TestClient(app)

    def test_post_without_content_type_defaults_to_json(self, client: TestClient):
        """Old clients (<=3.5.0) used httpx content= which omits
        Content-Type. The server should default to application/json."""
        # First create a flow so we can get a flow_run_id
        flow_resp = client.post("/api/flows/", json={"name": "ct-test-flow"})
        assert flow_resp.status_code == 201
        flow_id = flow_resp.json()["id"]

        flow_run_resp = client.post(
            "/api/flow_runs/",
            json={
                "flow_id": flow_id,
                "name": "ct-test-run",
                "state": {"type": "PENDING", "name": "Pending"},
            },
        )
        assert flow_run_resp.status_code == 201
        flow_run_id = flow_run_resp.json()["id"]

        # Simulate old client: send raw JSON bytes without Content-Type
        task_run_data = {
            "flow_run_id": flow_run_id,
            "task_key": "test-task",
            "dynamic_key": "0",
            "state": {"type": "PENDING", "name": "Pending"},
        }
        response = client.post(
            "/api/task_runs/",
            content=json.dumps(task_run_data),
        )
        assert response.status_code in (200, 201), (
            f"Expected 200/201 but got {response.status_code}: {response.text}"
        )

    def test_post_with_content_type_still_works(self, client: TestClient):
        """Requests that already include Content-Type should be unaffected."""
        flow_resp = client.post("/api/flows/", json={"name": "ct-test-flow-2"})
        assert flow_resp.status_code == 201
        flow_id = flow_resp.json()["id"]

        flow_run_resp = client.post(
            "/api/flow_runs/",
            json={
                "flow_id": flow_id,
                "name": "ct-test-run-2",
                "state": {"type": "PENDING", "name": "Pending"},
            },
        )
        assert flow_run_resp.status_code == 201
        flow_run_id = flow_run_resp.json()["id"]

        task_run_data = {
            "flow_run_id": flow_run_id,
            "task_key": "test-task-2",
            "dynamic_key": "0",
            "state": {"type": "PENDING", "name": "Pending"},
        }
        response = client.post(
            "/api/task_runs/",
            json=task_run_data,
        )
        assert response.status_code in (200, 201)
