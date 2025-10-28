from __future__ import annotations

from prefect.settings.models.server.ui import ServerUISettings


def test_ui_settings_defaults():
    """Test that UI settings have correct defaults"""
    settings = ServerUISettings()

    # Promotional content should be enabled by default
    assert settings.show_promotional_content is True


def test_ui_settings_can_disable_promotional_content():
    """Test that promotional content can be disabled"""
    settings = ServerUISettings(show_promotional_content=False)

    assert settings.show_promotional_content is False


def test_ui_settings_environment_variable_names():
    """Test that environment variable aliases work"""
    import os

    # Test PREFECT_SERVER_UI_SHOW_PROMOTIONAL_CONTENT
    os.environ["PREFECT_SERVER_UI_SHOW_PROMOTIONAL_CONTENT"] = "false"
    settings = ServerUISettings()
    assert settings.show_promotional_content is False

    # Clean up
    del os.environ["PREFECT_SERVER_UI_SHOW_PROMOTIONAL_CONTENT"]

    # Test legacy PREFECT_UI_SHOW_PROMOTIONAL_CONTENT alias
    os.environ["PREFECT_UI_SHOW_PROMOTIONAL_CONTENT"] = "false"
    settings = ServerUISettings()
    assert settings.show_promotional_content is False

    # Clean up
    del os.environ["PREFECT_UI_SHOW_PROMOTIONAL_CONTENT"]
