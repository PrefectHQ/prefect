"""
Pytest fixtures for SDK analytics tests.
"""

from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def telemetry_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable telemetry via environment variable."""
    monkeypatch.setenv("PREFECT_SERVER_ANALYTICS_ENABLED", "false")


@pytest.fixture
def telemetry_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure telemetry is enabled via environment variable."""
    monkeypatch.setenv("PREFECT_SERVER_ANALYTICS_ENABLED", "true")
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    # Clear CI variables
    from prefect._internal.analytics.ci_detection import CI_ENV_VARS

    for var in CI_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def do_not_track(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable DO_NOT_TRACK."""
    monkeypatch.setenv("DO_NOT_TRACK", "1")


@pytest.fixture
def ci_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a CI environment."""
    monkeypatch.setenv("CI", "true")


@pytest.fixture
def mock_amplitude() -> Generator[MagicMock, None, None]:
    """Mock the Amplitude client."""
    with patch("prefect._internal.analytics.client.Amplitude") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def clean_telemetry_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    """
    Reset telemetry state with a clean temporary directory.

    This fixture:
    1. Creates a fresh PREFECT_HOME in tmp_path
    2. Patches get_current_settings to use settings with the new home
    3. Resets telemetry initialization state

    Returns the path to the telemetry directory.
    """
    # Create a fresh Prefect home in tmp_path
    prefect_home = tmp_path / ".prefect"
    prefect_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PREFECT_HOME", str(prefect_home))

    # Create fresh settings that will pick up the new PREFECT_HOME
    from prefect.settings.models.root import Settings

    fresh_settings = Settings()

    # Patch get_current_settings to return our fresh settings
    with (
        patch(
            "prefect.settings.context.get_current_settings", return_value=fresh_settings
        ),
        patch("prefect.settings.get_current_settings", return_value=fresh_settings),
    ):
        # Clear any existing telemetry initialization state
        import prefect._internal.analytics

        prefect._internal.analytics._telemetry_initialized = False

        # Reset the Amplitude client
        import prefect._internal.analytics.client

        prefect._internal.analytics.client._amplitude_client = None
        prefect._internal.analytics.client._initialized = False

        # Clear the server analytics cache
        import prefect._internal.analytics.enabled

        prefect._internal.analytics.enabled._get_server_analytics_enabled.cache_clear()

        yield prefect_home / ".sdk_telemetry"
