"""
Tests for PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS setting validation.

This tests that the setting accepts numeric values (as the name implies) in addition
to standard timedelta formats.
"""

from __future__ import annotations

from datetime import timedelta

from prefect.settings import Settings
from prefect.settings.models.server.services import ServerServicesLateRunsSettings


class TestLateRunsAfterSecondsValidation:
    """Test that after_seconds accepts various input formats."""

    def test_numeric_string_via_env_var(self, monkeypatch):
        """Test that a plain numeric string like '5' is accepted and interpreted as seconds."""
        monkeypatch.setenv("PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS", "5")
        settings = Settings()
        assert settings.server.services.late_runs.after_seconds == timedelta(seconds=5)

    def test_numeric_string_with_decimals_via_env_var(self, monkeypatch):
        """Test that numeric strings with decimals work."""
        monkeypatch.setenv("PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS", "5.5")
        settings = Settings()
        assert settings.server.services.late_runs.after_seconds == timedelta(
            seconds=5.5
        )

    def test_server_alias_numeric_string(self, monkeypatch):
        """Test the PREFECT_SERVER_SERVICES_LATE_RUNS_AFTER_SECONDS alias with numeric value."""
        monkeypatch.setenv("PREFECT_SERVER_SERVICES_LATE_RUNS_AFTER_SECONDS", "10")
        settings = Settings()
        assert settings.server.services.late_runs.after_seconds == timedelta(seconds=10)

    def test_hms_format_still_works(self, monkeypatch):
        """Test that HH:MM:SS format continues to work (backward compatibility)."""
        monkeypatch.setenv("PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS", "00:00:05")
        settings = Settings()
        assert settings.server.services.late_runs.after_seconds == timedelta(seconds=5)

    def test_iso_duration_format_still_works(self, monkeypatch):
        """Test that ISO 8601 duration format continues to work."""
        monkeypatch.setenv("PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS", "PT5S")
        settings = Settings()
        assert settings.server.services.late_runs.after_seconds == timedelta(seconds=5)

    def test_numeric_integer_in_temporary_settings(self, monkeypatch):
        """Test that numeric integers work via environment variable (as used in tests)."""
        # Note: temporary_settings expects Setting objects, not dotted strings
        # So we test via environment variable instead
        monkeypatch.setenv("PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS", "60")
        settings = Settings()
        assert settings.server.services.late_runs.after_seconds == timedelta(seconds=60)

    def test_numeric_float_in_temporary_settings(self, monkeypatch):
        """Test that numeric floats work via environment variable."""
        monkeypatch.setenv("PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS", "5.5")
        settings = Settings()
        assert settings.server.services.late_runs.after_seconds == timedelta(
            seconds=5.5
        )

    def test_timedelta_in_temporary_settings(self, monkeypatch):
        """Test that timedelta strings continue to work via environment variable."""
        monkeypatch.setenv("PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS", "PT30S")
        settings = Settings()
        assert settings.server.services.late_runs.after_seconds == timedelta(seconds=30)

    def test_direct_construction_with_numeric(self):
        """Test direct construction of ServerServicesLateRunsSettings with numeric value."""
        # This should work when constructing the settings directly
        settings = ServerServicesLateRunsSettings(after_seconds=15)
        assert settings.after_seconds == timedelta(seconds=15)

    def test_direct_construction_with_numeric_string(self):
        """Test direct construction with numeric string."""
        settings = ServerServicesLateRunsSettings(after_seconds="20")
        assert settings.after_seconds == timedelta(seconds=20)

    def test_direct_construction_with_timedelta(self):
        """Test direct construction with timedelta object."""
        settings = ServerServicesLateRunsSettings(after_seconds=timedelta(seconds=25))
        assert settings.after_seconds == timedelta(seconds=25)

    def test_large_numeric_value(self, monkeypatch):
        """Test that large numeric values work correctly."""
        monkeypatch.setenv("PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS", "3600")
        settings = Settings()
        assert settings.server.services.late_runs.after_seconds == timedelta(hours=1)

    def test_zero_value(self, monkeypatch):
        """Test that zero is accepted."""
        monkeypatch.setenv("PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS", "0")
        settings = Settings()
        assert settings.server.services.late_runs.after_seconds == timedelta(seconds=0)

    def test_negative_value_allowed(self, monkeypatch):
        """Test that negative values are allowed (though unusual, timedelta allows it)."""
        # Pydantic/timedelta allows negative values, so we should too for flexibility
        monkeypatch.setenv("PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS", "-5")
        settings = Settings()
        assert settings.server.services.late_runs.after_seconds == timedelta(seconds=-5)
