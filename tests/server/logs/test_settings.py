from prefect.settings.models.server.logs import ServerLogsSettings


def test_logs_settings_defaults():
    """Test that logs settings have correct defaults"""
    settings = ServerLogsSettings()

    # Both streaming features should be disabled by default for safety
    assert settings.stream_out_enabled is False
    assert settings.stream_publishing_enabled is False


def test_logs_settings_can_be_enabled():
    """Test that logs settings can be enabled"""
    settings = ServerLogsSettings(
        stream_out_enabled=True, stream_publishing_enabled=True
    )

    assert settings.stream_out_enabled is True
    assert settings.stream_publishing_enabled is True


def test_logs_settings_environment_variable_names():
    """Test that environment variable aliases work"""
    import os

    # Test stream_out_enabled aliases
    os.environ["PREFECT_SERVER_LOGS_STREAM_OUT_ENABLED"] = "true"
    settings = ServerLogsSettings()
    assert settings.stream_out_enabled is True

    # Clean up
    del os.environ["PREFECT_SERVER_LOGS_STREAM_OUT_ENABLED"]

    # Test stream_publishing_enabled aliases
    os.environ["PREFECT_SERVER_LOGS_STREAM_PUBLISHING_ENABLED"] = "true"
    settings = ServerLogsSettings()
    assert settings.stream_publishing_enabled is True

    # Clean up
    del os.environ["PREFECT_SERVER_LOGS_STREAM_PUBLISHING_ENABLED"]
