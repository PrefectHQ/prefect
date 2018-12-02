import datetime
import json

import marshmallow
import pendulum
import pytest

from prefect.utilities.collections import DotDict
from prefect.utilities.serialization import DateTime, JSONCompatible

json_test_values = [
    1,
    [1, 2],
    "1",
    [1, "2"],
    {"x": 1},
    {"x": "1", "y": {"z": 3}},
    DotDict({"x": "1", "y": [DotDict(z=3)]}),
]


class TestJSONCompatibleField:
    class Schema(marshmallow.Schema):
        j = JSONCompatible()

    @pytest.mark.parametrize("value", json_test_values)
    def test_json_serialization(self, value):
        serialized = self.Schema().dump({"j": value})
        assert serialized["j"] == value

    @pytest.mark.parametrize("value", json_test_values)
    def test_json_deserialization(self, value):
        serialized = self.Schema().load({"j": value})
        assert serialized["j"] == value

    def test_validate_on_dump(self):
        with pytest.raises(marshmallow.ValidationError):
            self.Schema().dump({"j": lambda: 1})

    def test_validate_on_load(self):
        with pytest.raises(marshmallow.ValidationError):
            self.Schema().load({"j": lambda: 1})


class TestDateTimeField:
    class Schema(marshmallow.Schema):
        dt = DateTime()
        dt_none = DateTime(allow_none=True)

    def test_datetime_serialize(self):

        dt = pendulum.datetime(2020, 1, 1, 6, tz="EST")
        serialized = self.Schema().dump(dict(dt=dt))
        assert serialized["dt"] != str(dt)
        assert serialized["dt"] == str(dt.in_tz("utc"))

    def test_datetime_deserialize(self):

        dt = datetime.datetime(2020, 1, 1, 6)
        serialized = self.Schema().load(dict(dt=str(dt)))
        assert isinstance(serialized["dt"], pendulum.DateTime)
        assert serialized["dt"].tz == pendulum.tz.UTC

    def test_serialize_datetime_none(self):
        serialized = self.Schema().dump(dict(dt_none=None))
        assert serialized["dt_none"] is None

    def test_deserialize_datetime_none(self):
        deserialized = self.Schema().load(dict(dt_none=None))
        assert deserialized["dt_none"] is None
