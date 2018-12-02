import json
import marshmallow
import pytest
from prefect.utilities.serialization import JSONCompatibleField

json_test_values = [1, [1, 2], "1", [1, "2"], {"x": 1}, {"x": "1", "y": {"z": 3}}]


class TestJSONCompatibleField:
    class Schema(marshmallow.Schema):
        j = JSONCompatibleField()

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
