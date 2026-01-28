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
