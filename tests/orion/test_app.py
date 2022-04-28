from fastapi.testclient import TestClient

from prefect.orion.api.server import create_app
from prefect.settings import PREFECT_ORION_UI_API_URL


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
    assert response.json() == {"api_url": PREFECT_ORION_UI_API_URL.value()}
