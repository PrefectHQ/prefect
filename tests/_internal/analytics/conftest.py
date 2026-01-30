"""
Pytest fixtures for SDK analytics tests.
"""

from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def telemetry_disabled() -> Generator[None, None, None]:
    """Disable telemetry by mocking is_telemetry_enabled to return False."""
    with patch(
        "prefect._internal.analytics.enabled.is_telemetry_enabled", return_value=False
    ):
        yield


@pytest.fixture
def telemetry_enabled(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """
    Enable telemetry by clearing DO_NOT_TRACK and CI environment variables.

    Also mocks the service's server analytics check to return True.
    """
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)

    # Clear CI variables
    from prefect._internal.analytics.ci_detection import CI_ENV_VARS

    for var in CI_ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    # Mock the service's server check to return True
    with patch(
        "prefect._internal.analytics.service.AnalyticsService._check_server_analytics",
        return_value=True,
    ):
        yield


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
    4. Resets the AnalyticsService singleton

    Returns the path to the telemetry directory.
    """
    # Create a fresh Prefect home in tmp_path
    prefect_home = tmp_path / ".prefect"
    prefect_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PREFECT_HOME", str(prefect_home))

    # Create fresh settings that will pick up the new PREFECT_HOME
    from prefect.settings.models.root import Settings

    fresh_settings = Settings()

    # Patch get_current_settings everywhere it's used
    # Need to patch in all modules that import it at the top level
    with (
        patch(
            "prefect.settings.context.get_current_settings", return_value=fresh_settings
        ),
        patch("prefect.settings.get_current_settings", return_value=fresh_settings),
        patch(
            "prefect._internal.analytics.device_id.get_current_settings",
            return_value=fresh_settings,
        ),
        patch(
            "prefect._internal.analytics.milestones.get_current_settings",
            return_value=fresh_settings,
        ),
        patch(
            "prefect._internal.analytics.notice.get_current_settings",
            return_value=fresh_settings,
        ),
    ):
        # Clear any existing telemetry initialization state
        import prefect._internal.analytics

        prefect._internal.analytics._telemetry_initialized = False

        # Reset the Amplitude client
        import prefect._internal.analytics.client

        prefect._internal.analytics.client._amplitude_client = None
        prefect._internal.analytics.client._initialized = False

        # Reset the AnalyticsService singleton
        from prefect._internal.analytics.service import AnalyticsService

        AnalyticsService.reset()

        yield prefect_home / ".sdk_telemetry"


@pytest.fixture
def mock_analytics_service() -> Generator[MagicMock, None, None]:
    """Mock the AnalyticsService for testing event emission without background processing."""
    mock_service = MagicMock()

    with patch(
        "prefect._internal.analytics.service.AnalyticsService.instance",
        return_value=mock_service,
    ):
        yield mock_service
