"""
Tests for SDK analytics event emission.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prefect._internal.analytics import emit_integration_event
from prefect._internal.analytics.service import AnalyticsEvent


class TestEventEmission:
    """Test event emission via emit_sdk_event."""

    def test_emit_sdk_event_queues_event(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """emit_sdk_event should queue an event to the service."""
        mock_service = MagicMock()

        with patch(
            "prefect._internal.analytics.emit.AnalyticsService.instance",
            return_value=mock_service,
        ):
            from prefect._internal.analytics import emit_sdk_event

            result = emit_sdk_event("first_sdk_import")

            assert result is True
            mock_service.enqueue.assert_called_once()
            event = mock_service.enqueue.call_args[0][0]
            assert isinstance(event, AnalyticsEvent)
            assert event.event_name == "first_sdk_import"

    def test_emit_sdk_event_with_extra_properties(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """emit_sdk_event should pass extra properties in the event."""
        mock_service = MagicMock()

        with patch(
            "prefect._internal.analytics.emit.AnalyticsService.instance",
            return_value=mock_service,
        ):
            from prefect._internal.analytics import emit_sdk_event

            emit_sdk_event("first_sdk_import", extra_properties={"key": "value"})

            event = mock_service.enqueue.call_args[0][0]
            assert event.extra_properties == {"key": "value"}

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
            result = emit_sdk_event("first_sdk_import")

            assert result is False

    def test_emit_sdk_event_includes_device_id(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """emit_sdk_event should include the device ID in the event."""
        mock_service = MagicMock()

        with (
            patch(
                "prefect._internal.analytics.emit.AnalyticsService.instance",
                return_value=mock_service,
            ),
            patch(
                "prefect._internal.analytics.emit.get_or_create_device_id",
                return_value="test-device-id",
            ),
        ):
            from prefect._internal.analytics import emit_sdk_event

            emit_sdk_event("first_sdk_import")

            event = mock_service.enqueue.call_args[0][0]
            assert event.device_id == "test-device-id"


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

    def test_initialize_analytics_disabled_by_do_not_track(
        self, clean_telemetry_state: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """initialize_analytics should not emit events when DO_NOT_TRACK is set."""
        monkeypatch.setenv("DO_NOT_TRACK", "1")

        with patch("prefect._internal.analytics.emit_sdk_event") as mock_emit:
            import prefect._internal.analytics

            prefect._internal.analytics._telemetry_initialized = False

            from prefect._internal.analytics import initialize_analytics

            initialize_analytics()

            mock_emit.assert_not_called()

    def test_initialize_analytics_enabled(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """initialize_analytics should mark sdk_imported milestone when enabled."""
        with (
            patch(
                "prefect._internal.analytics._is_interactive_terminal",
                return_value=True,
            ),
            patch("prefect._internal.analytics.try_mark_milestone") as mock_milestone,
            patch("prefect._internal.analytics.maybe_show_telemetry_notice"),
        ):
            import prefect._internal.analytics

            prefect._internal.analytics._telemetry_initialized = False

            from prefect._internal.analytics import initialize_analytics

            initialize_analytics()

            mock_milestone.assert_called_once_with("first_sdk_import")

    def test_initialize_analytics_only_once(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """initialize_analytics should only run once."""
        with (
            patch(
                "prefect._internal.analytics._is_interactive_terminal",
                return_value=True,
            ),
            patch("prefect._internal.analytics.try_mark_milestone") as mock_milestone,
            patch("prefect._internal.analytics.maybe_show_telemetry_notice"),
        ):
            import prefect._internal.analytics

            prefect._internal.analytics._telemetry_initialized = False

            from prefect._internal.analytics import initialize_analytics

            initialize_analytics()
            initialize_analytics()  # Second call

            # Should only be called once
            mock_milestone.assert_called_once()

    def test_initialize_analytics_shows_notice(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """initialize_analytics should show telemetry notice."""
        with (
            patch(
                "prefect._internal.analytics._is_interactive_terminal",
                return_value=True,
            ),
            patch("prefect._internal.analytics.try_mark_milestone"),
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
            patch("prefect._internal.analytics.try_mark_milestone") as mock_milestone,
            patch(
                "prefect._internal.analytics.maybe_show_telemetry_notice"
            ) as mock_notice,
        ):
            import prefect._internal.analytics

            prefect._internal.analytics._telemetry_initialized = False

            from prefect._internal.analytics import initialize_analytics

            initialize_analytics()

            # Should not try to mark milestone for existing users
            mock_milestone.assert_not_called()
            # Should not show notice for existing users
            mock_notice.assert_not_called()

    def test_initialize_analytics_emits_for_new_user(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """initialize_analytics should mark sdk_imported milestone for new users."""
        # No existing user indicators - this is a new user

        with (
            patch(
                "prefect._internal.analytics._is_interactive_terminal",
                return_value=True,
            ),
            patch("prefect._internal.analytics.try_mark_milestone") as mock_milestone,
            patch(
                "prefect._internal.analytics.maybe_show_telemetry_notice"
            ) as mock_notice,
        ):
            import prefect._internal.analytics

            prefect._internal.analytics._telemetry_initialized = False

            from prefect._internal.analytics import initialize_analytics

            initialize_analytics()

            # Should mark sdk_imported milestone for new users
            mock_milestone.assert_called_once_with("first_sdk_import")
            # Should show notice for new users
            mock_notice.assert_called_once()


class TestIntegrationEventEmission:
    """Test emit_integration_event public API."""

    def test_event_namespacing(self, clean_telemetry_state: Path, telemetry_enabled):
        """Event name should be namespaced with 'integration:event_name'."""
        mock_service = MagicMock()

        with patch(
            "prefect._internal.analytics.emit.AnalyticsService.instance",
            return_value=mock_service,
        ):
            emit_integration_event("prefect-aws", "s3_block_created")

            mock_service.enqueue.assert_called_once()
            event = mock_service.enqueue.call_args[0][0]
            assert event.event_name == "prefect-aws:s3_block_created"

    def test_integration_property_included(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """Integration name should be included in extra_properties."""
        mock_service = MagicMock()

        with patch(
            "prefect._internal.analytics.emit.AnalyticsService.instance",
            return_value=mock_service,
        ):
            emit_integration_event("prefect-gcp", "bigquery_task_run")

            event = mock_service.enqueue.call_args[0][0]
            assert event.extra_properties["integration"] == "prefect-gcp"

    def test_extra_properties_merged(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """Extra properties should be merged with integration property."""
        mock_service = MagicMock()

        with patch(
            "prefect._internal.analytics.emit.AnalyticsService.instance",
            return_value=mock_service,
        ):
            emit_integration_event(
                "prefect-aws",
                "s3_block_created",
                extra_properties={"bucket": "my-bucket", "region": "us-east-1"},
            )

            event = mock_service.enqueue.call_args[0][0]
            assert event.extra_properties["integration"] == "prefect-aws"
            assert event.extra_properties["bucket"] == "my-bucket"
            assert event.extra_properties["region"] == "us-east-1"

    def test_returns_true_when_event_queued(
        self, clean_telemetry_state: Path, telemetry_enabled
    ):
        """Should return True when event is successfully queued."""
        mock_service = MagicMock()

        with patch(
            "prefect._internal.analytics.emit.AnalyticsService.instance",
            return_value=mock_service,
        ):
            result = emit_integration_event("prefect-aws", "s3_block_created")
            assert result is True

    def test_handles_exceptions(self, clean_telemetry_state: Path, telemetry_enabled):
        """Should handle exceptions without raising."""
        with patch(
            "prefect._internal.analytics.emit.get_or_create_device_id",
            side_effect=Exception("Test error"),
        ):
            result = emit_integration_event("prefect-aws", "s3_block_created")
            assert result is False
