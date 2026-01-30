"""
Tests for device ID generation and persistence.
"""

import uuid
from pathlib import Path

import pytest


class TestDeviceID:
    """Test device ID generation and persistence."""

    def test_generates_uuid(self, clean_telemetry_state: Path):
        """Should generate a valid UUID."""
        from prefect._internal.analytics.device_id import get_or_create_device_id

        device_id = get_or_create_device_id()

        # Should be a valid UUID
        uuid.UUID(device_id)

    def test_persists_device_id(self, clean_telemetry_state: Path):
        """Should persist device ID across calls."""
        from prefect._internal.analytics.device_id import get_or_create_device_id

        device_id_1 = get_or_create_device_id()
        device_id_2 = get_or_create_device_id()

        assert device_id_1 == device_id_2

    def test_stores_in_expected_location(self, clean_telemetry_state: Path):
        """Should store device ID in .sdk_telemetry directory."""
        from prefect._internal.analytics.device_id import get_or_create_device_id

        device_id = get_or_create_device_id()

        device_id_file = clean_telemetry_state / "device_id"
        assert device_id_file.exists()
        assert device_id_file.read_text().strip() == device_id

    def test_creates_directory_if_missing(self, clean_telemetry_state: Path):
        """Should create the .sdk_telemetry directory if it doesn't exist."""
        from prefect._internal.analytics.device_id import get_or_create_device_id

        # Ensure directory doesn't exist
        assert not clean_telemetry_state.exists()

        get_or_create_device_id()

        assert clean_telemetry_state.exists()
        assert (clean_telemetry_state / "device_id").exists()

    def test_regenerates_if_file_empty(
        self, clean_telemetry_state: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Should regenerate device ID if file is empty."""
        from prefect._internal.analytics.device_id import get_or_create_device_id

        # Create empty device ID file
        clean_telemetry_state.mkdir(parents=True, exist_ok=True)
        device_id_file = clean_telemetry_state / "device_id"
        device_id_file.write_text("")

        device_id = get_or_create_device_id()

        # Should have generated a new valid UUID
        uuid.UUID(device_id)
        assert device_id_file.read_text().strip() == device_id
