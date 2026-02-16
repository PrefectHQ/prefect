"""Tests for concurrency schema validation."""

import pytest
from pydantic import ValidationError

from prefect.client.schemas.objects import ConcurrencyLimitConfig, ConcurrencyOptions


class TestConcurrencyOptionsValidation:
    """Tests for ConcurrencyOptions grace_period_seconds validation."""

    def test_grace_period_seconds_default(self):
        """Test that grace_period_seconds defaults to None (falls back to server setting)."""
        options = ConcurrencyOptions(collision_strategy="ENQUEUE")
        assert options.grace_period_seconds is None

    def test_grace_period_seconds_minimum_boundary_valid(self):
        """Test that grace_period_seconds=60 is valid (minimum boundary)."""
        options = ConcurrencyOptions(
            collision_strategy="ENQUEUE", grace_period_seconds=60
        )
        assert options.grace_period_seconds == 60

    def test_grace_period_seconds_maximum_boundary_valid(self):
        """Test that grace_period_seconds=86400 is valid (maximum boundary)."""
        options = ConcurrencyOptions(
            collision_strategy="ENQUEUE", grace_period_seconds=86400
        )
        assert options.grace_period_seconds == 86400

    def test_grace_period_seconds_below_minimum_invalid(self):
        """Test that grace_period_seconds=59 raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            ConcurrencyOptions(collision_strategy="ENQUEUE", grace_period_seconds=59)
        assert "greater than or equal to 60" in str(exc_info.value)

    def test_grace_period_seconds_above_maximum_invalid(self):
        """Test that grace_period_seconds=86401 raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            ConcurrencyOptions(collision_strategy="ENQUEUE", grace_period_seconds=86401)
        assert "less than or equal to 86400" in str(exc_info.value)

    def test_grace_period_seconds_mid_range_valid(self):
        """Test that a mid-range value is valid."""
        options = ConcurrencyOptions(
            collision_strategy="ENQUEUE", grace_period_seconds=3600
        )
        assert options.grace_period_seconds == 3600


class TestConcurrencyLimitConfigValidation:
    """Tests for ConcurrencyLimitConfig grace_period_seconds validation."""

    def test_grace_period_seconds_default_none(self):
        """Test that grace_period_seconds defaults to None."""
        config = ConcurrencyLimitConfig(limit=1)
        assert config.grace_period_seconds is None

    def test_grace_period_seconds_minimum_boundary_valid(self):
        """Test that grace_period_seconds=60 is valid (minimum boundary)."""
        config = ConcurrencyLimitConfig(limit=1, grace_period_seconds=60)
        assert config.grace_period_seconds == 60

    def test_grace_period_seconds_maximum_boundary_valid(self):
        """Test that grace_period_seconds=86400 is valid (maximum boundary)."""
        config = ConcurrencyLimitConfig(limit=1, grace_period_seconds=86400)
        assert config.grace_period_seconds == 86400

    def test_grace_period_seconds_below_minimum_invalid(self):
        """Test that grace_period_seconds=59 raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            ConcurrencyLimitConfig(limit=1, grace_period_seconds=59)
        assert "greater than or equal to 60" in str(exc_info.value)

    def test_grace_period_seconds_above_maximum_invalid(self):
        """Test that grace_period_seconds=86401 raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            ConcurrencyLimitConfig(limit=1, grace_period_seconds=86401)
        assert "less than or equal to 86400" in str(exc_info.value)

    def test_grace_period_seconds_mid_range_valid(self):
        """Test that a mid-range value is valid."""
        config = ConcurrencyLimitConfig(limit=1, grace_period_seconds=3600)
        assert config.grace_period_seconds == 3600

    def test_collision_strategy_default(self):
        """Test that collision_strategy defaults to ENQUEUE."""
        config = ConcurrencyLimitConfig(limit=1)
        assert config.collision_strategy == "ENQUEUE"

    def test_collision_strategy_cancel_new(self):
        """Test that collision_strategy can be set to CANCEL_NEW."""
        config = ConcurrencyLimitConfig(limit=1, collision_strategy="CANCEL_NEW")
        assert config.collision_strategy == "CANCEL_NEW"


class TestConcurrencyOptionsSerialization:
    """Tests for ConcurrencyOptions serialization behavior.

    Regression tests for https://github.com/PrefectHQ/prefect/issues/19778
    """

    def test_grace_period_seconds_excluded_when_unset(self):
        """Test that grace_period_seconds is excluded when not explicitly set.

        When grace_period_seconds is not provided, model_dump(exclude_unset=True)
        should not include it in the output. This prevents API 422 errors.
        """
        options = ConcurrencyOptions(collision_strategy="ENQUEUE")
        payload = options.model_dump(mode="json", exclude_unset=True)

        assert "grace_period_seconds" not in payload

    def test_grace_period_seconds_included_when_set(self):
        """Test that grace_period_seconds IS included when explicitly set."""
        options = ConcurrencyOptions(
            collision_strategy="ENQUEUE", grace_period_seconds=120
        )
        payload = options.model_dump(mode="json", exclude_unset=True)

        assert "grace_period_seconds" in payload
        assert payload["grace_period_seconds"] == 120
