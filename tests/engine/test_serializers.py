import pytest
import base64
import json

import cloudpickle
import pendulum

from prefect.engine.serializers import (
    JSONSerializer,
    PandasSerializer,
    PickleSerializer,
)


class TestPickleSerializer:
    def test_serialize_returns_bytes(self):
        value = ["abc", 123, pendulum.now()]
        serialized = PickleSerializer().serialize(value)
        assert isinstance(serialized, bytes)

    def test_deserialize_returns_objects(self):
        value = ["abc", 123, pendulum.now()]
        serialized = PickleSerializer().serialize(value)
        deserialized = PickleSerializer().deserialize(serialized)
        assert deserialized == value

    def test_serialize_returns_cloudpickle(self):
        value = ["abc", 123, pendulum.now()]
        serialized = PickleSerializer().serialize(value)
        deserialized = cloudpickle.loads(serialized)
        assert deserialized == value

    def test_serialize_with_base64_encoded_cloudpickle(self):
        # for backwards compatibility, ensure encoded cloudpickles are
        # deserialized
        value = ["abc", 123, pendulum.now()]
        serialized = base64.b64encode(cloudpickle.dumps(value))
        deserialized = PickleSerializer().deserialize(serialized)
        assert deserialized == value

    def test_meaningful_errors_are_raised(self):
        # when deserialization fails, show the original error, not the
        # backwards-compatible error
        with pytest.raises(cloudpickle.pickle.UnpicklingError, match="stack underflow"):
            PickleSerializer().deserialize(b"bad-bytes")


class TestJSONSerializer:
    def test_serialize_returns_bytes(self):
        value = ["abc", 123]
        serialized = JSONSerializer().serialize(value)
        assert isinstance(serialized, bytes)

    def test_deserialize_returns_objects(self):
        value = ["abc", 123]
        serialized = JSONSerializer().serialize(value)
        deserialized = JSONSerializer().deserialize(serialized)
        assert deserialized == value

    def test_serialize_returns_json(self):
        value = ["abc", 123]
        serialized = JSONSerializer().serialize(value)
        assert serialized == json.dumps(value).encode()


class TestPandasSerializer:
    @pytest.fixture(scope="function")
    def input_dataframe(self):
        pd = pytest.importorskip("pandas", reason="Pandas not installed")
        return pd.DataFrame({"one": [1, 2, 3], "two": [4, 5, 6]})

    def test_complains_when_unavailable_file_type_specified(self):
        with pytest.raises(ValueError):
            PandasSerializer("blerg")

    @pytest.mark.parametrize("file_type", ["csv", "json"])
    def test_serialize_returns_bytes(self, file_type, input_dataframe):
        serialized = PandasSerializer(file_type).serialize(input_dataframe)
        assert isinstance(serialized, bytes)


def test_equality():
    assert PickleSerializer() == PickleSerializer()
    assert JSONSerializer() == JSONSerializer()
    assert PandasSerializer("csv") == PandasSerializer("csv")
    assert PandasSerializer("csv", write_kwargs={"one": 1}) == PandasSerializer(
        "csv", write_kwargs={"one": 1}
    )
    assert PickleSerializer() != JSONSerializer()
    assert PickleSerializer() != PandasSerializer("csv")
    assert PandasSerializer("csv") != PandasSerializer("parquet")
    assert PandasSerializer("csv", read_kwargs={"one": 1}) != PandasSerializer(
        "csv", read_kwargs={"one": 2}
    )
    assert PandasSerializer("csv", write_kwargs={"one": 1}) != PandasSerializer(
        "csv", write_kwargs={"one": 2}
    )
