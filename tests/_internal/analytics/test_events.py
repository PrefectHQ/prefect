"""
Tests for SDK analytics event emission.
"""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from prefect._internal.analytics import emit_integration_event


class TestEventEmission:
    """Test event emission via emit_sdk_event."""

    def test_emit_sdk_event_disabled(
        self, clean_telemetry_state: Path, telemetry_disabled
    ):
        """emit_sdk_event should return False when telemetry is disabled."""
        from prefect._internal.analytics import emit_sdk_event

        result = emit_sdk_event("sdk_imported")

        assert result is False

    def test_emit_sdk_event_enabled(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """emit_sdk_event should call track_event when enabled."""
        # Patch where track_event is imported (in emit.py)
        with patch("prefect._internal.analytics.emit.track_event") as mock_track:
            mock_track.return_value = True

            from prefect._internal.analytics import emit_sdk_event

            emit_sdk_event("sdk_imported")

            mock_track.assert_called_once()
            call_kwargs = mock_track.call_args[1]
            assert call_kwargs["event_name"] == "sdk_imported"

    def test_emit_sdk_event_with_extra_properties(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """emit_sdk_event should pass extra properties."""
        with patch("prefect._internal.analytics.emit.track_event") as mock_track:
            mock_track.return_value = True

            from prefect._internal.analytics import emit_sdk_event

            emit_sdk_event("sdk_imported", extra_properties={"key": "value"})

            call_kwargs = mock_track.call_args[1]
            assert call_kwargs["extra_properties"] == {"key": "value"}

    def test_emit_sdk_event_handles_exceptions(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """emit_sdk_event should handle exceptions without raising."""
        with patch(
            "prefect._internal.analytics.emit.get_or_create_device_id",
            side_effect=Exception("Test error"),
        ):
            from prefect._internal.analytics import emit_sdk_event

            # Should not raise
            result = emit_sdk_event("sdk_imported")

            assert result is False


class TestAnalyticsInitialization:
    """Test analytics initialization."""

    def test_initialize_analytics_skipped_in_non_tty(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """initialize_analytics should skip onboarding events in non-interactive terminals."""
        # Patch where functions are imported in __init__.py
        with (
            patch(
                "prefect._internal.analytics._is_interactive_terminal",
                return_value=False,
            ),
            patch("prefect._internal.analytics.emit_sdk_event") as mock_emit,
            patch(
                "prefect._internal.analytics.maybe_show_telemetry_notice"
            ) as mock_notice,
        ):
            import prefect._internal.analytics

            prefect._internal.analytics._telemetry_initialized = False

            from prefect._internal.analytics import initialize_analytics

            initialize_analytics()

            # Should not emit events or show notice in non-TTY
            mock_emit.assert_not_called()
            mock_notice.assert_not_called()

    def test_initialize_analytics_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """initialize_analytics should not emit events when disabled."""
        # Set up disabled telemetry environment BEFORE creating settings
        monkeypatch.setenv("PREFECT_SERVER_ANALYTICS_ENABLED", "false")
        prefect_home = tmp_path / ".prefect"
        prefect_home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("PREFECT_HOME", str(prefect_home))

        from prefect.settings.models.root import Settings

        fresh_settings = Settings()

        with (
            patch(
                "prefect.settings.context.get_current_settings",
                return_value=fresh_settings,
            ),
            patch("prefect.settings.get_current_settings", return_value=fresh_settings),
            patch("prefect._internal.analytics.emit_sdk_event") as mock_emit,
        ):
            import prefect._internal.analytics

            prefect._internal.analytics._telemetry_initialized = False

            from prefect._internal.analytics import initialize_analytics

            initialize_analytics()

            mock_emit.assert_not_called()

    def test_initialize_analytics_enabled(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """initialize_analytics should emit sdk_imported when enabled."""
        with (
            patch(
                "prefect._internal.analytics._is_interactive_terminal",
                return_value=True,
            ),
            patch("prefect._internal.analytics.emit_sdk_event") as mock_emit,
            patch("prefect._internal.analytics.maybe_show_telemetry_notice"),
        ):
            import prefect._internal.analytics

            prefect._internal.analytics._telemetry_initialized = False

            from prefect._internal.analytics import initialize_analytics

            initialize_analytics()

            mock_emit.assert_called_once_with("sdk_imported")

    def test_initialize_analytics_only_once(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """initialize_analytics should only run once."""
        with (
            patch(
                "prefect._internal.analytics._is_interactive_terminal",
                return_value=True,
            ),
            patch("prefect._internal.analytics.emit_sdk_event") as mock_emit,
            patch("prefect._internal.analytics.maybe_show_telemetry_notice"),
        ):
            import prefect._internal.analytics

            prefect._internal.analytics._telemetry_initialized = False

            from prefect._internal.analytics import initialize_analytics

            initialize_analytics()
            initialize_analytics()  # Second call

            # Should only be called once
            mock_emit.assert_called_once()

    def test_initialize_analytics_shows_notice(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """initialize_analytics should show telemetry notice."""
        with (
            patch(
                "prefect._internal.analytics._is_interactive_terminal",
                return_value=True,
            ),
            patch("prefect._internal.analytics.emit_sdk_event"),
            patch(
                "prefect._internal.analytics.maybe_show_telemetry_notice"
            ) as mock_notice,
        ):
            import prefect._internal.analytics

            prefect._internal.analytics._telemetry_initialized = False

            from prefect._internal.analytics import initialize_analytics

            initialize_analytics()

            mock_notice.assert_called_once()

    def test_initialize_analytics_skips_events_for_existing_user(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """initialize_analytics should not emit events for existing users."""
        # Create indicator of existing user
        prefect_home = clean_telemetry_state.parent
        (prefect_home / "profiles.toml").touch()

        with (
            patch(
                "prefect._internal.analytics._is_interactive_terminal",
                return_value=True,
            ),
            patch("prefect._internal.analytics.emit_sdk_event") as mock_emit,
            patch(
                "prefect._internal.analytics.maybe_show_telemetry_notice"
            ) as mock_notice,
        ):
            import prefect._internal.analytics

            prefect._internal.analytics._telemetry_initialized = False

            from prefect._internal.analytics import initialize_analytics

            initialize_analytics()

            # Should not emit sdk_imported for existing users
            mock_emit.assert_not_called()
            # Should not show notice for existing users
            mock_notice.assert_not_called()

    def test_initialize_analytics_emits_for_new_user(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """initialize_analytics should emit events for new users."""
        # No existing user indicators - this is a new user

        with (
            patch(
                "prefect._internal.analytics._is_interactive_terminal",
                return_value=True,
            ),
            patch("prefect._internal.analytics.emit_sdk_event") as mock_emit,
            patch(
                "prefect._internal.analytics.maybe_show_telemetry_notice"
            ) as mock_notice,
        ):
            import prefect._internal.analytics

            prefect._internal.analytics._telemetry_initialized = False

            from prefect._internal.analytics import initialize_analytics

            initialize_analytics()

            # Should emit sdk_imported for new users
            mock_emit.assert_called_once_with("sdk_imported")
            # Should show notice for new users
            mock_notice.assert_called_once()


class TestIntegrationEventEmission:
    """Test emit_integration_event public API."""

    def test_event_namespacing(self, clean_telemetry_state: Path, telemetry_enabled):
        """Event name should be namespaced with 'integration:event_name'."""
        with patch("prefect._internal.analytics.emit.track_event") as mock_track:
            mock_track.return_value = True

            emit_integration_event("prefect-aws", "s3_block_created")

            mock_track.assert_called_once()
            call_kwargs = mock_track.call_args[1]
            assert call_kwargs["event_name"] == "prefect-aws:s3_block_created"

    def test_integration_property_included(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """Integration name should be included in extra_properties."""
        with patch("prefect._internal.analytics.emit.track_event") as mock_track:
            mock_track.return_value = True

            emit_integration_event("prefect-gcp", "bigquery_task_run")

            call_kwargs = mock_track.call_args[1]
            assert call_kwargs["extra_properties"]["integration"] == "prefect-gcp"

    def test_extra_properties_merged(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """Extra properties should be merged with integration property."""
        with patch("prefect._internal.analytics.emit.track_event") as mock_track:
            mock_track.return_value = True

            emit_integration_event(
                "prefect-aws",
                "s3_block_created",
                extra_properties={"bucket": "my-bucket", "region": "us-east-1"},
            )

            call_kwargs = mock_track.call_args[1]
            extra_props: dict[str, Any] = call_kwargs["extra_properties"]
            assert extra_props["integration"] == "prefect-aws"
            assert extra_props["bucket"] == "my-bucket"
            assert extra_props["region"] == "us-east-1"

    def test_returns_false_when_telemetry_disabled(
        self, clean_telemetry_state: Path, telemetry_disabled
    ):
        """Should return False when telemetry is disabled."""
        result = emit_integration_event("prefect-aws", "s3_block_created")
        assert result is False

    def test_handles_exceptions(self, clean_telemetry_state: Path, telemetry_enabled):
        """Should handle exceptions without raising."""
        with patch(
            "prefect._internal.analytics.emit.get_or_create_device_id",
            side_effect=Exception("Test error"),
        ):
            result = emit_integration_event("prefect-aws", "s3_block_created")
            assert result is False
