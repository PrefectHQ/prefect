import pytest
from fastapi.testclient import TestClient

from prefect.server.api.server import create_app
from prefect.settings import (
    PREFECT_SERVER_CSRF_PROTECTION_ENABLED,
    PREFECT_UI_API_URL,
    temporary_settings,
)

# Steal some fixtures from the experimental test suite
from .._internal.compatibility.test_experimental import (
    enable_prefect_experimental_test_opt_in_setting,  # noqa: F401
    prefect_experimental_test_opt_in_setting,  # noqa: F401
)


def test_app_generates_correct_api_openapi_schema():
    """
    Test that helps detect situations in which our REST API reference docs
    fail to render properly.
    """
    schema = create_app(ephemeral=True).openapi()

    assert len(schema["paths"].keys()) > 1
    assert all([p.startswith("/api/") for p in schema["paths"].keys()])


def test_app_exposes_ui_settings():
    app = create_app()
    client = TestClient(app)
    response = client.get("/ui-settings")
    response.raise_for_status()
    json = response.json()

    flags = set(json.pop("flags"))
    assert flags == {
        "workers",
        "enhanced_cancellation",
        "artifacts_on_flow_run_graph",
        "states_on_flow_run_graph",
    }
    assert json == {
        "api_url": PREFECT_UI_API_URL.value(),
        "csrf_enabled": PREFECT_SERVER_CSRF_PROTECTION_ENABLED.value(),
    }


@pytest.mark.usefixtures("enable_prefect_experimental_test_opt_in_setting")
def test_app_exposes_ui_settings_with_experiments_enabled():
    app = create_app()
    client = TestClient(app)
    response = client.get("/ui-settings")
    response.raise_for_status()
    json = response.json()

    flags = set(json.pop("flags"))
    assert flags == {
        "test",
        "workers",
        "enhanced_cancellation",
        "artifacts_on_flow_run_graph",
        "states_on_flow_run_graph",
    }
    assert json == {
        "api_url": PREFECT_UI_API_URL.value(),
        "csrf_enabled": PREFECT_SERVER_CSRF_PROTECTION_ENABLED.value(),
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
