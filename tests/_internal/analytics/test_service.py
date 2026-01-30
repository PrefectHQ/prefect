"""
Tests for the background analytics service.
"""

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from prefect._internal.analytics.service import AnalyticsEvent, AnalyticsService


class TestAnalyticsService:
    """Test AnalyticsService behavior."""

    def test_singleton_instance(self, clean_telemetry_state: Path):
        """Service should be a singleton."""
        service1 = AnalyticsService.instance()
        service2 = AnalyticsService.instance()

        assert service1 is service2

    def test_reset_clears_instance(self, clean_telemetry_state: Path):
        """Reset should clear the singleton instance."""
        service1 = AnalyticsService.instance()
        AnalyticsService.reset()
        service2 = AnalyticsService.instance()

        assert service1 is not service2

    def test_enqueue_returns_immediately(self, clean_telemetry_state: Path):
        """enqueue() should return immediately (non-blocking)."""
        # Mock server check to be slow
        with patch.object(
            AnalyticsService,
            "_check_server_analytics",
            side_effect=lambda self: time.sleep(10),
        ):
            service = AnalyticsService.instance()

            start = time.monotonic()
            event = AnalyticsEvent(
                event_name="test_event",
                device_id="test-device",
            )
            service.enqueue(event)
            elapsed = time.monotonic() - start

            # Should return almost immediately (< 100ms)
            assert elapsed < 0.1

            # Cleanup
            service.shutdown(timeout=0.1)

    def test_quick_enabled_check_do_not_track(
        self, clean_telemetry_state: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Quick check should return False when DO_NOT_TRACK is set."""
        monkeypatch.setenv("DO_NOT_TRACK", "1")

        service = AnalyticsService.instance()
        assert service._quick_enabled_check() is False

    def test_quick_enabled_check_ci_environment(
        self, clean_telemetry_state: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Quick check should return False in CI environment."""
        monkeypatch.setenv("CI", "true")

        service = AnalyticsService.instance()
        assert service._quick_enabled_check() is False

    def test_quick_enabled_check_enabled(
        self, clean_telemetry_state: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Quick check should return True when no local disables are set."""
        monkeypatch.delenv("DO_NOT_TRACK", raising=False)
        monkeypatch.delenv("CI", raising=False)

        # Clear all CI environment variables
        from prefect._internal.analytics.ci_detection import CI_ENV_VARS

        for var in CI_ENV_VARS:
            monkeypatch.delenv(var, raising=False)

        service = AnalyticsService.instance()
        assert service._quick_enabled_check() is True

    def test_events_discarded_when_analytics_disabled(
        self, clean_telemetry_state: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Events should be discarded when server analytics is disabled."""
        monkeypatch.delenv("DO_NOT_TRACK", raising=False)
        monkeypatch.delenv("CI", raising=False)

        from prefect._internal.analytics.ci_detection import CI_ENV_VARS

        for var in CI_ENV_VARS:
            monkeypatch.delenv(var, raising=False)

        with patch(
            "prefect._internal.analytics.service.AnalyticsService._check_server_analytics",
            return_value=False,
        ):
            with patch("prefect._internal.analytics.service.track_event") as mock_track:
                service = AnalyticsService.instance()

                event = AnalyticsEvent(
                    event_name="test_event",
                    device_id="test-device",
                )
                service.enqueue(event)

                # Wait for analytics check to complete
                result = service.wait_for_analytics_check(timeout=2.0)
                assert result is False

                # Give the service time to drain the queue
                time.sleep(0.1)

                # track_event should not have been called
                mock_track.assert_not_called()

                service.shutdown(timeout=0.5)

    def test_events_forwarded_when_analytics_enabled(
        self, clean_telemetry_state: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Events should be forwarded to track_event when analytics is enabled."""
        monkeypatch.delenv("DO_NOT_TRACK", raising=False)
        monkeypatch.delenv("CI", raising=False)

        from prefect._internal.analytics.ci_detection import CI_ENV_VARS

        for var in CI_ENV_VARS:
            monkeypatch.delenv(var, raising=False)

        with patch(
            "prefect._internal.analytics.service.AnalyticsService._check_server_analytics",
            return_value=True,
        ):
            with patch("prefect._internal.analytics.service.track_event") as mock_track:
                service = AnalyticsService.instance()

                event = AnalyticsEvent(
                    event_name="test_event",
                    device_id="test-device",
                    extra_properties={"key": "value"},
                )
                service.enqueue(event)

                # Wait for analytics check to complete
                service.wait_for_analytics_check(timeout=2.0)

                # Give the service time to process the event
                time.sleep(0.2)

                mock_track.assert_called_once_with(
                    event_name="test_event",
                    device_id="test-device",
                    extra_properties={"key": "value"},
                )

                service.shutdown(timeout=0.5)

    def test_server_check_reads_local_setting_when_no_api_url(
        self, clean_telemetry_state: Path
    ):
        """When no API URL is configured, should read the local analytics setting."""
        service = AnalyticsService()

        mock_settings = type("Settings", (), {
            "api": type("API", (), {"url": None})(),
            "server": type("Server", (), {"analytics_enabled": True})(),
        })()

        with patch(
            "prefect.settings.context.get_current_settings",
            return_value=mock_settings,
        ):
            result = service._check_server_analytics()
            assert result is True

    def test_server_check_reads_local_setting_disabled_when_no_api_url(
        self, clean_telemetry_state: Path
    ):
        """When no API URL is configured and analytics is disabled locally, should return False."""
        service = AnalyticsService()

        mock_settings = type("Settings", (), {
            "api": type("API", (), {"url": None})(),
            "server": type("Server", (), {"analytics_enabled": False})(),
        })()

        with patch(
            "prefect.settings.context.get_current_settings",
            return_value=mock_settings,
        ):
            result = service._check_server_analytics()
            assert result is False

    def test_server_check_returns_true_when_analytics_enabled(
        self, clean_telemetry_state: Path
    ):
        """Server analytics check should return True when server has analytics enabled."""
        service = AnalyticsService()

        mock_settings = type("Settings", (), {
            "api": type("API", (), {"url": "http://localhost:4200/api"})(),
        })()
        mock_response = type("Response", (), {
            "raise_for_status": lambda self: None,
            "json": lambda self: {"server": {"analytics_enabled": True}},
        })()
        mock_client = type("Client", (), {
            "request": lambda self, method, path: mock_response,
            "__enter__": lambda self: self,
            "__exit__": lambda self, *args: None,
        })()

        with patch(
            "prefect.settings.context.get_current_settings",
            return_value=mock_settings,
        ), patch(
            "prefect.client.orchestration.get_client",
            return_value=mock_client,
        ):
            result = service._check_server_analytics()
            assert result is True

    def test_server_check_returns_false_on_error(self, clean_telemetry_state: Path):
        """Server analytics check should return False on error."""
        service = AnalyticsService()

        mock_settings = type("Settings", (), {
            "api": type("API", (), {"url": "http://localhost:4200/api"})(),
        })()

        with patch(
            "prefect.settings.context.get_current_settings",
            return_value=mock_settings,
        ), patch(
            "prefect.client.orchestration.get_client",
            side_effect=Exception("Connection error"),
        ):
            result = service._check_server_analytics()
            assert result is False

    def test_server_check_returns_false_when_analytics_disabled(
        self, clean_telemetry_state: Path
    ):
        """Server analytics check should return False when server has analytics disabled."""
        service = AnalyticsService()

        mock_settings = type("Settings", (), {
            "api": type("API", (), {"url": "http://localhost:4200/api"})(),
        })()
        mock_response = type("Response", (), {
            "raise_for_status": lambda self: None,
            "json": lambda self: {"server": {"analytics_enabled": False}},
        })()
        mock_client = type("Client", (), {
            "request": lambda self, method, path: mock_response,
            "__enter__": lambda self: self,
            "__exit__": lambda self, *args: None,
        })()

        with patch(
            "prefect.settings.context.get_current_settings",
            return_value=mock_settings,
        ), patch(
            "prefect.client.orchestration.get_client",
            return_value=mock_client,
        ):
            result = service._check_server_analytics()
            assert result is False

    def test_shutdown_flushes_pending_events(
        self, clean_telemetry_state: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Shutdown should process pending events."""
        monkeypatch.delenv("DO_NOT_TRACK", raising=False)
        monkeypatch.delenv("CI", raising=False)

        from prefect._internal.analytics.ci_detection import CI_ENV_VARS

        for var in CI_ENV_VARS:
            monkeypatch.delenv(var, raising=False)

        processed_events = []

        def capture_track(**kwargs):
            processed_events.append(kwargs)

        with patch(
            "prefect._internal.analytics.service.AnalyticsService._check_server_analytics",
            return_value=True,
        ):
            with patch(
                "prefect._internal.analytics.service.track_event",
                side_effect=capture_track,
            ):
                service = AnalyticsService.instance()

                # Queue multiple events
                for i in range(3):
                    event = AnalyticsEvent(
                        event_name=f"test_event_{i}",
                        device_id="test-device",
                    )
                    service.enqueue(event)

                # Wait for processing
                service.wait_for_analytics_check(timeout=2.0)
                time.sleep(0.3)

                # Shutdown should complete
                service.shutdown(timeout=2.0)

                # All events should have been processed
                assert len(processed_events) == 3

    def test_thread_starts_lazily(self, clean_telemetry_state: Path):
        """Background thread should only start when first event is queued."""
        service = AnalyticsService.instance()

        # Thread should not be started yet
        assert service._thread is None
        assert service._started is False

    def test_wait_for_analytics_check_timeout(self, clean_telemetry_state: Path):
        """wait_for_analytics_check should return None on timeout."""
        service = AnalyticsService()

        # Don't start the thread
        result = service.wait_for_analytics_check(timeout=0.01)

        assert result is None


class TestAnalyticsEvent:
    """Test AnalyticsEvent dataclass."""

    def test_event_creation(self):
        """Event should store all fields."""
        event = AnalyticsEvent(
            event_name="test_event",
            device_id="device-123",
            extra_properties={"key": "value"},
        )

        assert event.event_name == "test_event"
        assert event.device_id == "device-123"
        assert event.extra_properties == {"key": "value"}

    def test_event_optional_properties(self):
        """extra_properties should be optional."""
        event = AnalyticsEvent(
            event_name="test_event",
            device_id="device-123",
        )

        assert event.extra_properties is None


class TestForkSafety:
    """Test fork safety behavior."""

    def test_reset_registered_for_fork(self):
        """_reset_after_fork should be registered as a fork handler."""
        import os

        if hasattr(os, "register_at_fork"):
            # We can't easily test that it's registered, but we can verify
            # the function exists and can be called
            from prefect._internal.analytics.service import _reset_after_fork

            # Should not raise
            _reset_after_fork()
