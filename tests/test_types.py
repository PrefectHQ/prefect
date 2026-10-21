from __future__ import annotations

import datetime
import sys
import types
from typing import Any

import jsonschema
import pytest
from pydantic import BaseModel, ConfigDict, TypeAdapter

from prefect.types import (
    DurationOrSecondsTimeDelta,
    KeyValueLabelsField,
    NonNegativeTimeDelta,
    SecondsTimeDelta,
)
from prefect.types import _datetime as datetime_types
from prefect.types._datetime import human_friendly_diff


def test_allow_none_as_empty_dict():
    class Model(BaseModel):
        labels: KeyValueLabelsField

    assert Model(labels=None).labels == {}  # type: ignore[arg-type]


class MockOffsetTZInfo(datetime.tzinfo):
    """A minimal tzinfo subclass with a .name attribute holding an offset."""

    def __init__(self, name: str):
        self.name = name

    def utcoffset(self, dt: datetime.datetime | None) -> datetime.timedelta | None:
        if self.name.startswith("+"):
            sign = 1
        elif self.name.startswith("-"):
            sign = -1
        else:
            return None
        try:
            hours, minutes = map(int, self.name[1:].split(":"))
            return sign * datetime.timedelta(hours=hours, minutes=minutes)
        except ValueError:
            return None

    def dst(self, dt: datetime.datetime | None) -> datetime.timedelta | None:
        return None

    def tzname(self, dt: datetime.datetime | None) -> str | None:
        return self.name


def test_human_friendly_diff_with_offset_tzinfo():
    """Test that human_friendly_diff does not raise error with an offset tz name."""
    mock_tz = MockOffsetTZInfo(name="+05:30")
    dt_with_mock_offset = datetime.datetime.now().replace(tzinfo=mock_tz)

    # This call should raise ZoneInfoNotFoundError before the fix
    result = human_friendly_diff(dt_with_mock_offset)
    assert isinstance(result, str)


def test_seconds_timedelta_accepts_numeric_values():
    """Test that SecondsTimeDelta accepts numeric values as seconds."""

    class Model(BaseModel):
        duration: SecondsTimeDelta

    assert Model(duration=5).duration == datetime.timedelta(seconds=5)
    assert Model(duration="10").duration == datetime.timedelta(seconds=10)
    assert Model(duration="PT5S").duration == datetime.timedelta(seconds=5)


@pytest.mark.parametrize(
    "annotation", [DurationOrSecondsTimeDelta, NonNegativeTimeDelta]
)
def test_duration_schemas_distinguish_inputs_from_serialized_seconds(annotation: Any):
    adapter = TypeAdapter(annotation, config=ConfigDict(ser_json_timedelta="float"))
    input_validator = jsonschema.Draft202012Validator(adapter.json_schema())
    output_validator = jsonschema.Draft202012Validator(
        adapter.json_schema(mode="serialization")
    )

    for value in (60, "PT1M"):
        input_validator.validate(value)
        duration = adapter.validate_python(value)
        serialized = adapter.dump_python(duration, mode="json")
        assert serialized == 60
        output_validator.validate(serialized)

    assert not input_validator.is_valid(-1)
    assert not output_validator.is_valid("PT1M")


def test_now_uses_to_stdlib_on_python_313_plus(monkeypatch: pytest.MonkeyPatch):
    expected = datetime.datetime(2026, 4, 9, tzinfo=datetime.timezone.utc)

    class FakeZonedDateTimeResult:
        def to_stdlib(self) -> datetime.datetime:
            return expected

        def py_datetime(self) -> datetime.datetime:
            raise AssertionError("now() should not call py_datetime()")

    class FakeZonedDateTime:
        @staticmethod
        def now(tz: object) -> FakeZonedDateTimeResult:
            assert tz == "UTC"
            return FakeZonedDateTimeResult()

    monkeypatch.setattr(datetime_types.sys, "version_info", (3, 13))
    monkeypatch.setitem(
        sys.modules,
        "whenever",
        types.SimpleNamespace(ZonedDateTime=FakeZonedDateTime),
    )

    assert datetime_types.now("UTC") == expected


def test_now_falls_back_to_py_datetime_without_to_stdlib(
    monkeypatch: pytest.MonkeyPatch,
):
    expected = datetime.datetime(2026, 4, 9, tzinfo=datetime.timezone.utc)

    class FakeZonedDateTimeResult:
        def py_datetime(self) -> datetime.datetime:
            return expected

    class FakeZonedDateTime:
        @staticmethod
        def now(tz: object) -> FakeZonedDateTimeResult:
            assert tz == "UTC"
            return FakeZonedDateTimeResult()

    monkeypatch.setattr(datetime_types.sys, "version_info", (3, 13))
    monkeypatch.setitem(
        sys.modules,
        "whenever",
        types.SimpleNamespace(ZonedDateTime=FakeZonedDateTime),
    )

    assert datetime_types.now("UTC") == expected
