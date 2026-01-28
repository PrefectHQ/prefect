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
        from prefect.sdk_analytics._client import _get_event_properties

        props = _get_event_properties()

        assert props["prefect_version"] == prefect.__version__

    def test_event_properties_include_python_version(self, clean_telemetry_state: Path):
        """Event properties should include Python version."""
        import platform

        from prefect.sdk_analytics._client import _get_event_properties

        props = _get_event_properties()

        assert props["python_version"] == platform.python_version()

    def test_event_properties_include_platform(self, clean_telemetry_state: Path):
        """Event properties should include platform."""
        import platform

        from prefect.sdk_analytics._client import _get_event_properties

        props = _get_event_properties()

        assert props["platform"] == platform.system()

    def test_event_properties_include_architecture(self, clean_telemetry_state: Path):
        """Event properties should include architecture."""
        import platform

        from prefect.sdk_analytics._client import _get_event_properties

        props = _get_event_properties()

        assert props["architecture"] == platform.machine()

    def test_track_event_no_api_key(self, clean_telemetry_state: Path):
        """track_event should return False when API key is not configured."""
        from prefect.sdk_analytics._client import track_event

        # The default API key is a placeholder, so initialization should fail
        result = track_event(
            event_name="sdk_imported",
            device_id="test-device-id",
        )

        assert result is False

    def test_track_event_with_mock_amplitude(self, clean_telemetry_state: Path):
        """track_event should send events when Amplitude is configured."""
        mock_instance = MagicMock()

        with (
            patch("prefect.sdk_analytics._client.AMPLITUDE_API_KEY", "test-api-key"),
            patch.dict(
                "sys.modules",
                {
                    "amplitude": MagicMock(
                        Amplitude=MagicMock(return_value=mock_instance),
                        Config=MagicMock(),
                        BaseEvent=MagicMock(),
                    )
                },
            ),
        ):
            # Reset initialization state
            import prefect.sdk_analytics._client

            prefect.sdk_analytics._client._initialized = False
            prefect.sdk_analytics._client._amplitude_client = None

            from prefect.sdk_analytics._client import track_event

            result = track_event(
                event_name="sdk_imported",
                device_id="test-device-id",
            )

            assert result is True
            mock_instance.track.assert_called_once()

    def test_track_event_includes_extra_properties(self, clean_telemetry_state: Path):
        """track_event should include extra properties."""
        mock_instance = MagicMock()
        mock_event_class = MagicMock()

        with (
            patch("prefect.sdk_analytics._client.AMPLITUDE_API_KEY", "test-api-key"),
            patch.dict(
                "sys.modules",
                {
                    "amplitude": MagicMock(
                        Amplitude=MagicMock(return_value=mock_instance),
                        Config=MagicMock(),
                        BaseEvent=mock_event_class,
                    )
                },
            ),
        ):
            # Reset initialization state
            import prefect.sdk_analytics._client

            prefect.sdk_analytics._client._initialized = False
            prefect.sdk_analytics._client._amplitude_client = None

            from prefect.sdk_analytics._client import track_event

            track_event(
                event_name="sdk_imported",
                device_id="test-device-id",
                extra_properties={"custom_key": "custom_value"},
            )

            # Verify BaseEvent was created with custom property
            call_kwargs = mock_event_class.call_args[1]
            assert call_kwargs["event_properties"]["custom_key"] == "custom_value"

    def test_track_event_handles_exceptions_silently(self, clean_telemetry_state: Path):
        """track_event should handle exceptions without raising."""
        with (
            patch("prefect.sdk_analytics._client.AMPLITUDE_API_KEY", "test-api-key"),
            patch.dict(
                "sys.modules",
                {
                    "amplitude": MagicMock(
                        Amplitude=MagicMock(side_effect=Exception("Test error")),
                        Config=MagicMock(),
                    )
                },
            ),
        ):
            # Reset initialization state
            import prefect.sdk_analytics._client

            prefect.sdk_analytics._client._initialized = False
            prefect.sdk_analytics._client._amplitude_client = None

            from prefect.sdk_analytics._client import track_event

            # Should not raise
            result = track_event(
                event_name="sdk_imported",
                device_id="test-device-id",
            )

            assert result is False
