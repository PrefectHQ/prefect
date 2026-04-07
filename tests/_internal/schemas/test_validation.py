import datetime

import dateutil.rrule
import pytest

from prefect._internal.schemas.validators import (
    DEFAULT_RRULE_ANCHOR,
    normalize_rrule_string,
    validate_parameter_openapi_schema,
    validate_values_conform_to_schema,
)

# Tests for validate_schema function


def test_validate_schema_with_valid_schema():
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    # Should not raise any exception
    validate_parameter_openapi_schema(schema, {"enforce_parameter_schema": True})


def test_validate_schema_with_invalid_schema():
    schema = {"type": "object", "properties": {"name": {"type": "nonexistenttype"}}}
    with pytest.raises(ValueError) as excinfo:
        validate_parameter_openapi_schema(schema, {"enforce_parameter_schema": True})
    assert "The provided schema is not a valid json schema." in str(excinfo.value)
    assert (
        "Schema error: 'nonexistenttype' is not valid under any of the given schemas"
        in str(excinfo.value)
    )


def test_validate_schema_with_none_schema():
    # Should not raise any exception
    validate_parameter_openapi_schema(None, {"enforce_parameter_schema": True})


# Tests for validate_values_conform_to_schema function


def test_validate_values_conform_to_schema_valid_values_valid_schema():
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    values = {"name": "John"}
    # Should not raise any exception
    validate_values_conform_to_schema(values, schema)


def test_validate_values_conform_to_schema_invalid_values_valid_schema():
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    values = {"name": 123}
    with pytest.raises(ValueError) as excinfo:
        validate_values_conform_to_schema(values, schema)
    assert "Validation failed for field 'name'." in str(excinfo.value)
    assert "Failure reason: 123 is not of type 'string'" in str(excinfo.value)


def test_validate_values_conform_to_schema_valid_values_invalid_schema():
    schema = {"type": "object", "properties": {"name": {"type": "nonexistenttype"}}}
    values = {"name": "John"}
    with pytest.raises(ValueError) as excinfo:
        validate_values_conform_to_schema(values, schema)
    assert "The provided schema is not a valid json schema." in str(excinfo.value)
    assert (
        "Schema error: 'nonexistenttype' is not valid under any of the given schemas"
        in str(excinfo.value)
    )


def test_validate_values_conform_to_schema_ignore_required():
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    values = {}
    # Should not raise any exception
    validate_values_conform_to_schema(values, schema, ignore_required=True)

    # Make sure that the schema is not modified
    assert schema == {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }


def test_validate_values_conform_to_schema_none_values_or_schema():
    # Should not raise any exception for either of these
    validate_values_conform_to_schema(None, {"type": "string"})
    validate_values_conform_to_schema({"name": "John"}, None)
    validate_values_conform_to_schema(None, None)


# Tests for normalize_rrule_string (#21362)


class TestNormalizeRRuleString:
    """Unit tests for the rrule normalization helper used by the
    deployment schedule write path. See PrefectHQ/prefect#21362."""

    FIXED_NOW = datetime.datetime(2026, 4, 6, 12, 34, 56)

    @pytest.mark.parametrize(
        "rule, expected_dtstart",
        [
            # MINUTELY/SECONDLY without COUNT get a phase-equivalent
            # recent anchor, computed as the largest k * period before now.
            ("FREQ=MINUTELY;INTERVAL=5", "DTSTART:20260406T123000\n"),
            ("FREQ=MINUTELY", "DTSTART:20260406T123400\n"),
            ("FREQ=SECONDLY;INTERVAL=30", "DTSTART:20260406T123430\n"),
            ("FREQ=SECONDLY", "DTSTART:20260406T123456\n"),
        ],
    )
    def test_high_frequency_rules_get_recent_anchor(self, rule, expected_dtstart):
        assert (
            normalize_rrule_string(rule, now=self.FIXED_NOW) == expected_dtstart + rule
        )

    @pytest.mark.parametrize(
        "rule",
        [
            # Anything we can't safely advance keeps the legacy 2020 anchor.
            "FREQ=HOURLY",
            "FREQ=HOURLY;INTERVAL=2",
            "FREQ=DAILY;BYHOUR=9,17",
            "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO",
            "FREQ=MONTHLY;BYMONTHDAY=15",
            "FREQ=YEARLY;BYMONTH=3;BYDAY=2MO",
            # COUNT counts from dtstart — never advance.
            "FREQ=MINUTELY;COUNT=10",
            "FREQ=SECONDLY;COUNT=100",
        ],
    )
    def test_unsafe_shapes_get_legacy_anchor(self, rule):
        out = normalize_rrule_string(rule, now=self.FIXED_NOW)
        assert out == f"DTSTART:20200101T000000\n{rule}"

    def test_already_anchored_rule_is_unchanged(self):
        original = "DTSTART:19970902T090000\nRRULE:FREQ=YEARLY;COUNT=2;BYDAY=TU"
        assert normalize_rrule_string(original, now=self.FIXED_NOW) == original

    def test_rdate_only_string_gets_legacy_anchor(self):
        # Rrulesets without an explicit DTSTART fall through to the
        # safe path. Phase-advancing arbitrary rrulesets is out of scope.
        original = "RDATE:20221012T134000Z,20221012T230000Z"
        out = normalize_rrule_string(original, now=self.FIXED_NOW)
        assert out == f"DTSTART:20200101T000000\n{original}"

    @pytest.mark.parametrize(
        "rule",
        [
            "FREQ=MINUTELY;INTERVAL=5",
            "FREQ=SECONDLY;INTERVAL=30",
            "FREQ=HOURLY",
            "FREQ=DAILY;BYHOUR=9,17",
            "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO",
            "FREQ=YEARLY;BYMONTH=3;BYDAY=2MO",
            "FREQ=MINUTELY;COUNT=10",
        ],
    )
    def test_normalized_rule_preserves_forward_occurrence_set(self, rule):
        """The whole point: the normalized rrule must produce the same
        occurrences from `now` forward as the legacy implicit-anchor
        parsing it replaces. This is the correctness invariant."""
        legacy = dateutil.rrule.rrulestr(rule, dtstart=DEFAULT_RRULE_ANCHOR)
        normalized = dateutil.rrule.rrulestr(
            normalize_rrule_string(rule, now=self.FIXED_NOW)
        )
        legacy_dates = list(legacy.xafter(self.FIXED_NOW, count=10))
        new_dates = list(normalized.xafter(self.FIXED_NOW, count=10))
        assert legacy_dates == new_dates

    def test_recent_anchor_keeps_dateutil_cache_small(self):
        """Smoke test for the memory win — a normalized MINUTELY rule
        should populate dateutil's `_cache` with a tiny number of
        entries (~tens), not the millions that the 2020 anchor produced.
        See PrefectHQ/prefect#21362 review thread for the original
        ~660k / ~37 MB measurement."""
        normalized = normalize_rrule_string(
            "FREQ=MINUTELY;INTERVAL=5", now=self.FIXED_NOW
        )
        rr = dateutil.rrule.rrulestr(normalized, cache=True)
        list(rr.xafter(self.FIXED_NOW, count=20))
        # 20 requested + a small look-ahead window from dateutil's
        # generator. The legacy 2020-anchored variant would have ~660k
        # here. Cap generously to keep the test stable.
        assert len(rr._cache) < 200  # pyright: ignore[reportPrivateUsage]
