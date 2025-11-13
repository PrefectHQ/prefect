"""
Tests for the SecondsTimeDelta annotated type.

This type allows timedelta fields to accept numeric values (interpreted as seconds)
in addition to standard timedelta formats.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import BaseModel, ValidationError

from prefect.types import SecondsTimeDelta


class TestSecondsTimeDelta:
    """Test the SecondsTimeDelta annotated type."""

    def test_accepts_int(self):
        """Test that integers are accepted and interpreted as seconds."""

        class Model(BaseModel):
            duration: SecondsTimeDelta

        m = Model(duration=5)
        assert m.duration == timedelta(seconds=5)

    def test_accepts_float(self):
        """Test that floats are accepted and interpreted as seconds."""

        class Model(BaseModel):
            duration: SecondsTimeDelta

        m = Model(duration=5.5)
        assert m.duration == timedelta(seconds=5.5)

    def test_accepts_numeric_string(self):
        """Test that numeric strings are accepted and interpreted as seconds."""

        class Model(BaseModel):
            duration: SecondsTimeDelta

        m = Model(duration="10")
        assert m.duration == timedelta(seconds=10)

    def test_accepts_float_string(self):
        """Test that float strings are accepted and interpreted as seconds."""

        class Model(BaseModel):
            duration: SecondsTimeDelta

        m = Model(duration="7.5")
        assert m.duration == timedelta(seconds=7.5)

    def test_accepts_timedelta(self):
        """Test that timedelta objects are accepted."""

        class Model(BaseModel):
            duration: SecondsTimeDelta

        m = Model(duration=timedelta(minutes=2))
        assert m.duration == timedelta(minutes=2)

    def test_accepts_iso_8601_duration(self):
        """Test that ISO 8601 duration strings are accepted."""

        class Model(BaseModel):
            duration: SecondsTimeDelta

        m = Model(duration="PT5S")
        assert m.duration == timedelta(seconds=5)

    def test_accepts_time_format(self):
        """Test that HH:MM:SS format strings are accepted."""

        class Model(BaseModel):
            duration: SecondsTimeDelta

        m = Model(duration="00:00:05")
        assert m.duration == timedelta(seconds=5)

    def test_accepts_zero(self):
        """Test that zero is accepted."""

        class Model(BaseModel):
            duration: SecondsTimeDelta

        m = Model(duration=0)
        assert m.duration == timedelta(seconds=0)

        m = Model(duration="0")
        assert m.duration == timedelta(seconds=0)

    def test_accepts_negative_values(self):
        """Test that negative values are accepted."""

        class Model(BaseModel):
            duration: SecondsTimeDelta

        m = Model(duration=-5)
        assert m.duration == timedelta(seconds=-5)

        m = Model(duration="-5")
        assert m.duration == timedelta(seconds=-5)

    def test_rejects_invalid_strings(self):
        """Test that invalid strings are rejected."""

        class Model(BaseModel):
            duration: SecondsTimeDelta

        with pytest.raises(ValidationError):
            Model(duration="invalid")

        with pytest.raises(ValidationError):
            Model(duration="5x")

    def test_large_values(self):
        """Test that large numeric values work correctly."""

        class Model(BaseModel):
            duration: SecondsTimeDelta

        m = Model(duration=3600)
        assert m.duration == timedelta(hours=1)

        m = Model(duration="86400")
        assert m.duration == timedelta(days=1)

    def test_preserves_precision(self):
        """Test that float precision is preserved."""

        class Model(BaseModel):
            duration: SecondsTimeDelta

        m = Model(duration=1.5)
        assert m.duration.total_seconds() == 1.5

        m = Model(duration="2.25")
        assert m.duration.total_seconds() == 2.25

    def test_default_value(self):
        """Test that default values work."""

        class Model(BaseModel):
            duration: SecondsTimeDelta = timedelta(seconds=10)

        m = Model()
        assert m.duration == timedelta(seconds=10)

    def test_optional(self):
        """Test that optional fields work."""

        class Model(BaseModel):
            duration: SecondsTimeDelta | None = None

        m = Model()
        assert m.duration is None

        m = Model(duration=5)
        assert m.duration == timedelta(seconds=5)
