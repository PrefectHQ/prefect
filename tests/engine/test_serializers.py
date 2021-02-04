import base64
import gzip
import json
import lzma

import cloudpickle
import pendulum
import pytest

from prefect.engine.serializers import (
    CompressedSerializer,
    DateTimeSerializer,
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


class TestDateTimeSerializer:
    def test_serialize_returns_bytes(self):
        value = pendulum.now()
        serialized = DateTimeSerializer().serialize(value)
        assert isinstance(serialized, bytes)

    def test_deserialize_returns_objects(self):
        value = pendulum.now()
        serialized = DateTimeSerializer().serialize(value)
        deserialized = DateTimeSerializer().deserialize(serialized)
        assert deserialized == value


class TestPandasSerializer:
    @pytest.fixture(scope="function")
    def input_dataframe(self):
        pd = pytest.importorskip("pandas", reason="Pandas not installed")
        return pd.DataFrame({"one": [1, 2, 3], "two": [4, 5, 6]})

    def test_complains_when_unavailable_file_type_specified(self):
        pd = pytest.importorskip("pandas", reason="Pandas not installed")
        with pytest.raises(ValueError):
            PandasSerializer("blerg")

    @pytest.mark.parametrize("file_type", ["csv", "json"])
    def test_serialize_returns_bytes(self, file_type, input_dataframe):
        pd = pytest.importorskip("pandas", reason="Pandas not installed")
        serialized = PandasSerializer(file_type).serialize(input_dataframe)
        assert isinstance(serialized, bytes)

    def test_serialize_deserialize_is_invariant(self, input_dataframe):
        file_type = "json"
        pd = pytest.importorskip("pandas", reason="Pandas not installed")
        serializer = PandasSerializer(file_type)
        serialized = serializer.serialize(input_dataframe)
        deserialized = serializer.deserialize(serialized)
        pd.testing.assert_frame_equal(input_dataframe, deserialized)

    def test_serialize_kwargs_work_as_expected(self, input_dataframe):
        pd = pytest.importorskip("pandas", reason="Pandas not installed")
        serializer = PandasSerializer(
            "csv", serialize_kwargs={"sep": ":", "index": False}
        )
        serialized = serializer.serialize(input_dataframe)
        deserialized = serializer.deserialize(serialized)
        expected = pd.DataFrame({"one:two": ["1:4", "2:5", "3:6"]})
        pd.testing.assert_frame_equal(expected, deserialized)

    def test_deserialize_kwargs_work_as_expected(self, input_dataframe):
        pd = pytest.importorskip("pandas", reason="Pandas not installed")
        np = pytest.importorskip("numpy", reason="numpy not installed")
        serializer = PandasSerializer("csv", deserialize_kwargs={"na_values": [3, 5]})
        serialized = serializer.serialize(input_dataframe)
        deserialized = serializer.deserialize(serialized)
        expected = pd.DataFrame(
            {"Unnamed: 0": [0, 1, 2], "one": [1, 2, np.nan], "two": [4, np.nan, 6]}
        )
        pd.testing.assert_frame_equal(expected, deserialized)


class TestCompressedSerializer:
    COMPRESSION_KWARGS = {
        "compress": lzma.compress,
        "decompress": lzma.decompress,
        "compress_kwargs": {"format": lzma.FORMAT_XZ},
        "decompress_kwargs": {"format": lzma.FORMAT_AUTO},
    }

    def test_serialize_returns_bytes(self):
        value = ["abc", 123, pendulum.now()]
        serialized = CompressedSerializer(
            PickleSerializer(), **self.COMPRESSION_KWARGS
        ).serialize(value)
        assert isinstance(serialized, bytes)

    def test_deserialize_returns_objects(self):
        value = ["abc", 123, pendulum.now()]
        serialized = CompressedSerializer(
            PickleSerializer(), **self.COMPRESSION_KWARGS
        ).serialize(value)
        deserialized = CompressedSerializer(
            PickleSerializer(), **self.COMPRESSION_KWARGS
        ).deserialize(serialized)
        assert deserialized == value

    def test_pickle_serialize_returns_compressed_cloudpickle(self):
        value = ["abc", 123, pendulum.now()]
        serialized = CompressedSerializer(
            PickleSerializer(), **self.COMPRESSION_KWARGS
        ).serialize(value)
        deserialized = cloudpickle.loads(lzma.decompress(serialized))
        assert deserialized == value

    def test_pickle_deserialize_raises_meaningful_errors(self):
        # when pickle deserialization involving decompression fails, show the original
        # error, not the backwards-compatible error
        with pytest.raises(cloudpickle.pickle.UnpicklingError, match="stack underflow"):
            CompressedSerializer(
                PickleSerializer(), **self.COMPRESSION_KWARGS
            ).deserialize(lzma.compress(b"bad-bytes"))


def test_equality():
    COMPRESSION_KWARGS = {
        "compress": lzma.compress,
        "decompress": lzma.decompress,
        "compress_kwargs": {"format": lzma.FORMAT_XZ},
        "decompress_kwargs": {"format": lzma.FORMAT_AUTO},
    }

    assert PickleSerializer() == PickleSerializer()
    assert JSONSerializer() == JSONSerializer()
    assert CompressedSerializer(
        PickleSerializer(), **COMPRESSION_KWARGS
    ) == CompressedSerializer(PickleSerializer(), **COMPRESSION_KWARGS)
    assert PickleSerializer() != JSONSerializer()
    assert CompressedSerializer(
        PickleSerializer(), **COMPRESSION_KWARGS
    ) != CompressedSerializer(JSONSerializer(), **COMPRESSION_KWARGS)
    assert CompressedSerializer(
        PickleSerializer(), **COMPRESSION_KWARGS
    ) != CompressedSerializer(
        PickleSerializer(), compress=gzip.compress, decompress=gzip.decompress
    )


def test_pandas_serializer_equality():
    pd = pytest.importorskip("pandas", reason="Pandas not installed")
    assert PickleSerializer() != PandasSerializer("csv")
    assert PandasSerializer("csv") == PandasSerializer("csv")
    assert PandasSerializer("csv", serialize_kwargs={"one": 1}) == PandasSerializer(
        "csv", serialize_kwargs={"one": 1}
    )
    assert PandasSerializer("csv") != PandasSerializer("parquet")
    assert PandasSerializer("csv", deserialize_kwargs={"one": 1}) != PandasSerializer(
        "csv", deserialize_kwargs={"one": 2}
    )
    assert PandasSerializer("csv", serialize_kwargs={"one": 1}) != PandasSerializer(
        "csv", serialize_kwargs={"one": 2}
    )
