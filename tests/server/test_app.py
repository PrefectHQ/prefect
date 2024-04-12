from typing import Set

import pytest
from prefect._vendor.fastapi.testclient import TestClient

from prefect.server.api.server import create_app
from prefect.settings import (
    PREFECT_SERVER_CSRF_PROTECTION_ENABLED,
    PREFECT_UI_API_URL,
    SETTING_VARIABLES,
    Setting,
    Settings,
    temporary_settings,
)


@pytest.fixture()
def example_experiments(
    monkeypatch: pytest.MonkeyPatch,
) -> Set[str]:
    enabled_experiments = {
        "michelson_morley",
        "pavlov_dog",
        "double_slit",
    }

    disabled_experiments = {
        "schrodinger_cat",
        "rutherford_gold_foil",
    }

    # Clear any existing settings that start with the
    # PREFECT_EXPERIMENTAL_ENABLE_ prefix
    keys_to_remove = [
        key
        for key in SETTING_VARIABLES
        if key.startswith("PREFECT_EXPERIMENTAL_ENABLE_")
    ]
    for key in keys_to_remove:
        del SETTING_VARIABLES[key]
        setting_name = f"prefect.settings.Settings.{key}"
        if hasattr(Settings, key):
            monkeypatch.delattr(setting_name, raising=False)

    # Add in the example experiments.
    for experiment in enabled_experiments | disabled_experiments:
        enabled = experiment in enabled_experiments
        setting = Setting(bool, default=False)
        setting.name = f"PREFECT_EXPERIMENTAL_ENABLE_{experiment.upper()}"
        monkeypatch.setitem(SETTING_VARIABLES, setting.name, setting)
        monkeypatch.setattr(
            f"prefect.settings.Settings.{setting.name}", enabled, raising=False
        )

    return enabled_experiments


def test_app_generates_correct_api_openapi_schema():
    """
    Test that helps detect situations in which our REST API reference docs
    fail to render properly.
    """
    schema = create_app(ephemeral=True).openapi()

    assert len(schema["paths"].keys()) > 1
    assert all([p.startswith("/api/") for p in schema["paths"].keys()])


def test_app_exposes_ui_settings(example_experiments: Set[str]):
    app = create_app()
    client = TestClient(app)
    response = client.get("/ui-settings")
    response.raise_for_status()
    json = response.json()
    assert json["api_url"] == PREFECT_UI_API_URL.value()
    assert set(json["flags"]) == example_experiments


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
