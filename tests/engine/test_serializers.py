import base64
import json

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
    @pytest.mark.parametrize("format", ["bz2", "gzip", "lzma", "zlib"])
    def test_constructor_accepts_standard_formats(self, format) -> None:
        serializer = PickleSerializer()
        module = pytest.importorskip(format)
        assert CompressedSerializer(
            serializer, format=module.__name__
        ) == CompressedSerializer(
            serializer, compress=module.compress, decompress=module.decompress
        )

    def test_constructor_rejects_missing_format_libs(self) -> None:
        with pytest.raises(ImportError, match="'foobar' is not installed"):
            CompressedSerializer(PickleSerializer(), format="foobar")

    def test_constructor_rejects_format_libs_without_compression(self) -> None:
        with pytest.raises(
            ValueError,
            match="'prefect' module does not have 'compress' and 'decompress'",
        ):
            CompressedSerializer(PickleSerializer(), format="prefect")

    def test_constructor_requires_format_or_functions(self) -> None:
        with pytest.raises(ValueError):
            CompressedSerializer(PickleSerializer())

    def test_constructor_rejects_format_and_functions_when_both_specified(self) -> None:
        with pytest.raises(ValueError):
            CompressedSerializer(
                PickleSerializer(),
                format="gzip",
                compress=lambda: True,
                decompress=lambda: True,
            )

    def test_serialize_returns_bytes(self) -> None:
        value = ["abc", 123, pendulum.now()]
        serialized = CompressedSerializer(PickleSerializer(), format="bz2").serialize(
            value
        )
        assert isinstance(serialized, bytes)

    def test_deserialize_returns_objects(self) -> None:
        value = ["abc", 123, pendulum.now()]
        serialized = CompressedSerializer(PickleSerializer(), format="gzip").serialize(
            value
        )
        deserialized = CompressedSerializer(
            PickleSerializer(), format="gzip"
        ).deserialize(serialized)
        assert deserialized == value

    def test_deserialize_with_functions_returns_objects(self) -> None:
        lzma = pytest.importorskip("lzma")
        value = ["abc", 123, pendulum.now()]
        serializer = CompressedSerializer(
            PickleSerializer(),
            compress=lzma.compress,
            decompress=lzma.decompress,
            compress_kwargs={"format": lzma.FORMAT_XZ},
            decompress_kwargs={"format": lzma.FORMAT_AUTO},
        )
        serialized = serializer.serialize(value)
        deserialized = serializer.deserialize(serialized)
        assert deserialized == value

    def test_pickle_serialize_returns_compressed_cloudpickle(self) -> None:
        zlib = pytest.importorskip("zlib")
        value = ["abc", 123, pendulum.now()]
        serialized = CompressedSerializer(PickleSerializer(), format="zlib").serialize(
            value
        )
        deserialized = cloudpickle.loads(zlib.decompress(serialized))
        assert deserialized == value

    def test_pickle_deserialize_raises_meaningful_errors(self) -> None:
        zlib = pytest.importorskip("zlib")
        # when pickle deserialization involving decompression fails, show the original
        # error, not the backwards-compatible error
        with pytest.raises(cloudpickle.pickle.UnpicklingError, match="stack underflow"):
            CompressedSerializer(PickleSerializer(), format="zlib").deserialize(
                zlib.compress(b"bad-bytes")
            )


def test_equality():
    assert PickleSerializer() == PickleSerializer()
    assert JSONSerializer() == JSONSerializer()
    assert PickleSerializer() != JSONSerializer()


def test_compressed_serializer_equality() -> None:
    gzip = pytest.importorskip("gzip")
    assert CompressedSerializer(
        PickleSerializer(), format="bz2"
    ) == CompressedSerializer(PickleSerializer(), format="bz2")
    assert CompressedSerializer(
        PickleSerializer(), format="bz2"
    ) != CompressedSerializer(JSONSerializer(), format="bz2")
    assert CompressedSerializer(
        PickleSerializer(), format="bz2"
    ) != CompressedSerializer(
        PickleSerializer(), compress=gzip.compress, decompress=gzip.decompress
    )
    assert CompressedSerializer(
        PickleSerializer(), compress=gzip.compress, decompress=gzip.decompress
    ) != CompressedSerializer(
        PickleSerializer(),
        compress=gzip.compress,
        decompress=gzip.decompress,
        compress_kwargs={"compresslevel": 8},
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
