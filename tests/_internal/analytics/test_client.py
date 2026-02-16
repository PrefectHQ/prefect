"""
Tests for Amplitude client wrapper.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestAmplitudeClient:
    """Test Amplitude client behavior."""

    def test_event_properties_include_version(self, clean_telemetry_state: Path):
        """Event properties should include Prefect version."""
        import prefect
        from prefect._internal.analytics.client import _get_event_properties

        props = _get_event_properties()

        assert props["prefect_version"] == prefect.__version__

    def test_event_properties_include_python_version(self, clean_telemetry_state: Path):
        """Event properties should include Python version."""
        import platform

        from prefect._internal.analytics.client import _get_event_properties

        props = _get_event_properties()

        assert props["python_version"] == platform.python_version()

    def test_event_properties_include_platform(self, clean_telemetry_state: Path):
        """Event properties should include platform."""
        import platform

        from prefect._internal.analytics.client import _get_event_properties

        props = _get_event_properties()

        assert props["platform"] == platform.system()

    def test_event_properties_include_architecture(self, clean_telemetry_state: Path):
        """Event properties should include architecture."""
        import platform

        from prefect._internal.analytics.client import _get_event_properties

        props = _get_event_properties()

        assert props["architecture"] == platform.machine()

    def test_track_event_no_api_key(self, clean_telemetry_state: Path):
        """track_event should return False when API key is not configured."""
        from prefect._internal.analytics.client import track_event

        # The default API key is a placeholder, so initialization should fail
        result = track_event(
            event_name="first_sdk_import",
            device_id="test-device-id",
        )

        assert result is False

    def test_track_event_with_mock_amplitude(self, clean_telemetry_state: Path):
        """track_event should send events when Amplitude is configured."""
        import prefect._internal.analytics.client as client_module

        mock_client = MagicMock()

        with patch.object(client_module, "AMPLITUDE_API_KEY", "test-api-key"):
            # Reset initialization state
            client_module._initialized = False
            client_module._amplitude_client = None

            # Mock the Amplitude class to return our mock client
            with patch.object(
                client_module, "Amplitude", return_value=mock_client
            ) as mock_amplitude_class:
                result = client_module.track_event(
                    event_name="first_sdk_import",
                    device_id="test-device-id",
                )

                assert result is True
                mock_amplitude_class.assert_called_once()
                mock_client.track.assert_called_once()

    def test_track_event_includes_extra_properties(self, clean_telemetry_state: Path):
        """track_event should include extra properties."""
        import prefect._internal.analytics.client as client_module

        mock_client = MagicMock()
        captured_event = None

        def capture_track(event):
            nonlocal captured_event
            captured_event = event

        mock_client.track = capture_track

        with patch.object(client_module, "AMPLITUDE_API_KEY", "test-api-key"):
            # Reset initialization state
            client_module._initialized = False
            client_module._amplitude_client = None

            with patch.object(client_module, "Amplitude", return_value=mock_client):
                client_module.track_event(
                    event_name="first_sdk_import",
                    device_id="test-device-id",
                    extra_properties={"custom_key": "custom_value"},
                )

                # Verify the event was created with custom property
                assert captured_event is not None
                assert captured_event.event_properties["custom_key"] == "custom_value"

    def test_track_event_handles_exceptions_silently(self, clean_telemetry_state: Path):
        """track_event should handle exceptions without raising."""
        import prefect._internal.analytics.client as client_module

        with patch.object(client_module, "AMPLITUDE_API_KEY", "test-api-key"):
            # Reset initialization state
            client_module._initialized = False
            client_module._amplitude_client = None

            with patch.object(
                client_module, "Amplitude", side_effect=Exception("Test error")
            ):
                # Should not raise
                result = client_module.track_event(
                    event_name="first_sdk_import",
                    device_id="test-device-id",
                )

                assert result is False
