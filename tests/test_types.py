from __future__ import annotations

import datetime
import sys
import types
from uuid import uuid4

import pytest
from pydantic import BaseModel

from prefect.client.schemas import actions as client_actions
from prefect.client.schemas import objects as client_objects
from prefect.server.schemas import actions as server_actions
from prefect.server.schemas import core as server_core
from prefect.types import KeyValueLabelsField, SecondsTimeDelta
from prefect.types import _datetime as datetime_types
from prefect.types._datetime import human_friendly_diff
from prefect.types.names import (
    raise_on_name_alphanumeric_dashes_only,
    raise_on_name_alphanumeric_dashes_underscores_only,
    raise_on_name_alphanumeric_underscores_only,
)


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


def test_now_uses_to_stdlib_on_python_313_plus(monkeypatch: pytest.MonkeyPatch):
    expected = datetime.datetime(2026, 4, 9, tzinfo=datetime.UTC)

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
    expected = datetime.datetime(2026, 4, 9, tzinfo=datetime.UTC)

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


@pytest.mark.parametrize(
    "validator",
    [
        raise_on_name_alphanumeric_dashes_only,
        raise_on_name_alphanumeric_underscores_only,
        raise_on_name_alphanumeric_dashes_underscores_only,
    ],
)
@pytest.mark.parametrize("value", ["name\n", "name\nname"])
def test_name_validators_reject_newlines(validator, value: str):
    with pytest.raises(ValueError, match="must only contain"):
        validator(value)


@pytest.mark.parametrize(
    "create_model",
    [client_actions.BlockDocumentCreate, server_actions.BlockDocumentCreate],
)
def test_block_document_create_rejects_trailing_newline_name(create_model):
    with pytest.raises(ValueError, match="must only contain"):
        create_model(
            name="new-block\n", data={}, block_schema_id=uuid4(), block_type_id=uuid4()
        )


def test_block_document_response_accepts_previously_stored_trailing_newline():
    block_document = client_objects.BlockDocument(
        name="legacy-block\n", data={}, block_schema_id=uuid4(), block_type_id=uuid4()
    )
    assert block_document.name == "legacy-block\n"


@pytest.mark.parametrize(
    "input_model", [client_objects.FlowRunInput, server_core.FlowRunInput]
)
def test_flow_run_input_response_accepts_previously_stored_trailing_newline(
    input_model,
):
    flow_run_input = input_model(flow_run_id=uuid4(), key="legacy-key\n", value="value")
    assert flow_run_input.key == "legacy-key\n"


@pytest.mark.parametrize(
    "input_model", [client_objects.FlowRunInput, server_core.FlowRunInput]
)
def test_flow_run_input_response_still_rejects_invalid_keys(input_model):
    with pytest.raises(ValueError, match="must only contain"):
        input_model(flow_run_id=uuid4(), key="legacy key", value="value")
