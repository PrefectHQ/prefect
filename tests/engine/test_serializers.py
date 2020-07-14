import base64
import json
from datetime import datetime

import cloudpickle
import pandas as pd
import pendulum
import pytest

from prefect.engine.serializers import (
    DataFrameSerializer,
    JSONSerializer,
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


class TestDataFrameSerializer:
    simple_df = pd.DataFrame(
        {"strs": ["hello", "world"], "ints": [1, 2], "bools": [True, False]}
    )

    now = datetime.now()
    datetime_df = pd.DataFrame({"id": ["abc123", "def456"], "timestamp": [now, now]})

    @pytest.mark.parametrize("value", [simple_df, datetime_df])
    def test_serialize_returns_bytes(self, value):
        serialized = DataFrameSerializer().serialize(value)
        assert isinstance(serialized, bytes)

    def test_deserialize_returns_objects_simple(self):
        # Only testing the simple case here because CSV is a bad storage format
        # Other tests check for better value to value comparison
        serialized = DataFrameSerializer().serialize(self.simple_df)
        deserialized = DataFrameSerializer().deserialize(serialized)

        # Pandas API to_csv adds the index as a column
        # Since nothing fancy is going on with the index, we can simply drop it
        # before we compare the IO
        deserialized = deserialized.drop("Unnamed: 0", axis=1)
        assert deserialized.equals(self.simple_df)

    def test_round_trip_with_kwargs(self):
        # Parquet is better for datetimes
        # Not 100% perfect, but at least has a datetime type unlike text CSV
        # Not 100% perfect because it has less precision for microseconds
        serializer = DataFrameSerializer(
            format="parquet", serialize_kwargs={"allow_truncated_timestamps": True}
        )
        serialized = serializer.serialize(self.datetime_df)
        deserialized = serializer.deserialize(serialized)

        # Reduce precision of datetimes in original dataframe before compare
        # The precision that parquet supports is to the thousandths place
        comparison_df = self.datetime_df.copy()
        comparison_df.timestamp = comparison_df.timestamp.apply(
            lambda value: value.replace(microsecond=value.microsecond // 1000 * 1000)
        )

        assert deserialized.equals(comparison_df)


def test_equality():
    assert PickleSerializer() == PickleSerializer()
    assert JSONSerializer() == JSONSerializer()
    assert PickleSerializer() != JSONSerializer()
    assert DataFrameSerializer() == DataFrameSerializer()
    assert DataFrameSerializer() != PickleSerializer()
