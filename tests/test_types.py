from __future__ import annotations

import datetime

from pydantic import BaseModel

from prefect.types import KeyValueLabelsField
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
