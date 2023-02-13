import pytest
from fastapi.testclient import TestClient

from prefect.server.api.server import create_app
from prefect.settings import PREFECT_UI_API_URL

from .._internal.compatibility.test_experimental import (
    enable_prefect_experimental_test_opt_in_setting,  # pylint: disable=unused-import
)
from .._internal.compatibility.test_experimental import (
    prefect_experimental_test_opt_in_setting,  # pylint: disable=unused-import
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
    assert response.json() == {
        "api_url": PREFECT_UI_API_URL.value(),
        "flags": ["work_pools"],
    }


@pytest.mark.usefixtures("enable_prefect_experimental_test_opt_in_setting")
def test_app_exposes_ui_settings_with_experiments_enabled():
    app = create_app()
    client = TestClient(app)
    response = client.get("/ui-settings")
    response.raise_for_status()
    json = response.json()
    assert json["api_url"] == PREFECT_UI_API_URL.value()
    assert set(json["flags"]) == {"test", "work_pools"}
