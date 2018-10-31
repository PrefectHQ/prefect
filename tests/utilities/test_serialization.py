import json
import marshmallow
import pytest
from prefect.utilities.serialization import JSONField

json_test_values = [1, [1, 2], "1", [1, "2"], {"x": 1}, {"x": "1", "y": {"z": 3}}]


class TestJSONField:
    class Schema(marshmallow.Schema):
        json = JSONField()
        json_limited = JSONField(max_size=10)

    @pytest.mark.parametrize("value", json_test_values)
    def test_json_serialization(self, value):
        serialized = self.Schema().dump({"json": value})
        assert serialized["json"] == json.dumps(value)

    @pytest.mark.parametrize("value", json_test_values)
    def test_json_deserialization(self, value):
        serialized = self.Schema().load({"json": json.dumps(value)})
        assert serialized["json"] == value

    def test_max_size_serialization(self):
        with pytest.raises(ValueError) as exc:
            self.Schema().dump({"json_limited": "x" * 100})
        assert "payload exceeds max size" in str(exc).lower()

    def test_max_size_deserialization(self):
        with pytest.raises(ValueError) as exc:
            self.Schema().load({"json_limited": "x" * 100})
        assert "payload exceeds max size" in str(exc).lower()
