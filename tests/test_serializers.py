import json
import prefect.serializers as serializers
import datetime


def test_JSONSerializer_on_simple_string():
    s = serializers.JSONSerializer
    x = "x"
    j = s.serialize(x)
    assert j == '"x"'
    assert s.deserialize(j) == x


def test_JSONSerializer_on_dict():
    s = serializers.JSONSerializer
    x = {"1": "a", "b": [2, {"3": 4}]}
    j = s.serialize(x)
    assert json.loads(j) == x
    assert s.deserialize(j) == x


def test_JSONSerializer_on_prefect_json_types():
    s = serializers.JSONSerializer
    x = datetime.datetime(2018, 1, 1)
    j = s.serialize(x)
    assert json.loads(j) == x
    assert s.deserialize(j) == x
