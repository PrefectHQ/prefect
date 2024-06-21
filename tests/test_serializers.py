import base64
import json
import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, ValidationError, field_validator

from prefect.serializers import (
    CompressedSerializer,
    JSONSerializer,
    PickleSerializer,
    Serializer,
    prefect_json_object_decoder,
    prefect_json_object_encoder,
)
from prefect.testing.utilities import exceptions_equal
from prefect.utilities.dispatch import get_registry_for_type

# Freeze a UUID for deterministic tests
TEST_UUID = uuid.UUID("a53e3495-d681-4a53-84b8-9d9542f7237c")


class MyModel(BaseModel):
    x: int
    y: uuid.UUID


@dataclass
class MyDataclass:
    x: int
    y: str


@dataclass
class MyDataclassBytes:
    x: int
    y: bytes


# Simple test cases that all serializers should support roundtrips for
SERIALIZER_TEST_CASES = [
    1,
    "test",
    {"foo": "bar"},
    ["x", "y"],
    TEST_UUID,
    MyModel(x=1, y=TEST_UUID),
    MyDataclass(x=1, y="test"),
    "test string".encode("utf-8"),
    "test string".encode("ASCII"),
    MyDataclassBytes(x=1, y="test".encode("utf-8")),
]

# Exceptions are a little trickier to compare, so we test them separately
EXCEPTION_TEST_CASES = [Exception("foo"), ValueError("bar")]

complex_str = """
def dog(some_param: str) -> int:
    print('woof!' + some_param)
    print('These are complex chars: !@#$%^&*()_+-')
"""


class TestBaseSerializer:
    @pytest.fixture(autouse=True)
    def restore_dispatch_registry(self):
        # Clears serializers defined in tests below to prevent warnings on collision
        before = get_registry_for_type(Serializer).copy()

        yield

        registry = get_registry_for_type(Serializer)
        registry.clear()
        registry.update(before)

    def test_serializers_do_not_allow_extra_fields(self):
        class Foo(Serializer):
            type: str = "foo"

            def dumps(self, obj):
                pass

            def loads(self, obj):
                pass

        with pytest.raises(ValidationError):
            Foo(x="test")

    def test_serializers_can_be_created_by_dict(self):
        class Foo(BaseModel):
            serializer: Serializer

        class Bar(Serializer):
            type: str = "bar"

            def dumps(self, obj):
                pass

            def loads(self, obj):
                pass

        model = Foo(serializer={"type": "bar"})
        assert isinstance(model.serializer, Bar)

    def test_serializers_can_be_created_by_object(self):
        class Foo(BaseModel):
            serializer: Serializer

        class Bar(Serializer):
            type: str = "bar"

            def dumps(self, obj):
                pass

            def loads(self, obj):
                pass

        model = Foo(serializer=Bar())
        assert isinstance(model.serializer, Bar)

    def test_serializers_can_be_created_by_type_string(self):
        class Foo(BaseModel):
            serializer: Serializer

            @field_validator("serializer", mode="before")
            def cast_type_to_dict(cls, value):
                if isinstance(value, str):
                    return {"type": value}
                return value

        class Bar(Serializer):
            type: str = "bar"

            def dumps(self, obj):
                pass

            def loads(self, obj):
                pass

        model = Foo(serializer="bar")
        assert isinstance(model.serializer, Bar)


class TestPickleSerializer:
    @pytest.mark.parametrize("data", SERIALIZER_TEST_CASES)
    def test_simple_roundtrip(self, data):
        serializer = PickleSerializer()
        serialized = serializer.dumps(data)
        assert serializer.loads(serialized) == data

    @pytest.mark.parametrize("data", EXCEPTION_TEST_CASES)
    def test_exception_roundtrip(self, data):
        serializer = PickleSerializer()
        serialized = serializer.dumps(data)
        assert exceptions_equal(serializer.loads(serialized), data)

    @pytest.mark.parametrize("data", SERIALIZER_TEST_CASES)
    def test_simple_roundtrip_with_builtin_pickle(self, data):
        serializer = PickleSerializer(picklelib="pickle")
        serialized = serializer.dumps(data)
        assert serializer.loads(serialized) == data

    def test_picklelib_must_be_string(self):
        import pickle

        with pytest.raises(ValueError):
            PickleSerializer(picklelib=pickle)

    def test_picklelib_is_used(self, monkeypatch):
        dumps = MagicMock(return_value=b"test")
        loads = MagicMock(return_value="test")
        monkeypatch.setattr("pickle.dumps", dumps)
        monkeypatch.setattr("pickle.loads", loads)
        serializer = PickleSerializer(picklelib="pickle")
        serializer.dumps("test")
        dumps.assert_called_once_with("test")
        serializer.loads(b"test")
        loads.assert_called_once_with(base64.decodebytes(b"test"))

    def test_picklelib_must_implement_dumps(self, monkeypatch):
        import pickle

        monkeypatch.delattr(pickle, "dumps")
        with pytest.raises(
            ValueError,
            match="Pickle library at 'pickle' does not have a 'dumps' method.",
        ):
            PickleSerializer(picklelib="pickle")

    def test_picklelib_must_implement_loads(self, monkeypatch):
        import pickle

        monkeypatch.delattr(pickle, "loads")
        with pytest.raises(
            ValueError,
            match="Pickle library at 'pickle' does not have a 'loads' method.",
        ):
            PickleSerializer(picklelib="pickle")


class TestJSONSerializer:
    @pytest.mark.parametrize("data", SERIALIZER_TEST_CASES)
    def test_simple_roundtrip(self, data):
        serializer = JSONSerializer()
        serialized = serializer.dumps(data)
        assert serializer.loads(serialized) == data

    @pytest.mark.parametrize("data", EXCEPTION_TEST_CASES)
    def test_exception_roundtrip(self, data):
        serializer = JSONSerializer()
        serialized = serializer.dumps(data)
        assert exceptions_equal(serializer.loads(serialized), data)

    @pytest.mark.parametrize(
        "data",
        [
            complex_str.encode("utf-8"),
            complex_str.encode("ASCII"),
            complex_str.encode("latin_1"),
            [complex_str.encode("utf-8")],
            {"key": complex_str.encode("ASCII")},
        ],
    )
    def test_simple_roundtrip_with_complex_bytes(self, data):
        serializer = JSONSerializer()
        serialized = serializer.dumps(data)
        assert serializer.loads(serialized) == data

    def test_allows_orjson(self):
        # orjson does not support hooks
        serializer = JSONSerializer(
            jsonlib="orjson", object_encoder=None, object_decoder=None
        )
        serialized = serializer.dumps("test")
        assert serializer.loads(serialized) == "test"

    def test_uses_alternative_json_library(self, monkeypatch):
        dumps_mock = MagicMock()
        loads_mock = MagicMock()
        monkeypatch.setattr("orjson.dumps", dumps_mock)
        monkeypatch.setattr("orjson.loads", loads_mock)
        serializer = JSONSerializer(jsonlib="orjson")
        serializer.dumps("test")
        serializer.loads(b"test")
        dumps_mock.assert_called_once_with("test", default=prefect_json_object_encoder)
        loads_mock.assert_called_once_with(
            "test", object_hook=prefect_json_object_decoder
        )

    def test_allows_custom_encoder(self, monkeypatch):
        fake_object_encoder = MagicMock(return_value="foobar!")
        prefect_object_encoder = MagicMock()

        monkeypatch.setattr(
            "prefect.serializers.fake_object_encoder",
            fake_object_encoder,
            raising=False,
        )
        monkeypatch.setattr(
            "prefect.serializers.prefect_json_object_encoder",
            prefect_object_encoder,
        )

        serializer = JSONSerializer(
            object_encoder="prefect.serializers.fake_object_encoder"
        )

        # Encoder hooks are only called for unsupported objects
        obj = uuid.uuid4()
        result = serializer.dumps(obj)
        assert result == b'"foobar!"'
        prefect_object_encoder.assert_not_called()
        fake_object_encoder.assert_called_once_with(obj)

    def test_allows_custom_decoder(self, monkeypatch):
        fake_object_decoder = MagicMock(return_value="test")
        prefect_object_decoder = MagicMock()

        monkeypatch.setattr(
            "prefect.serializers.fake_object_decoder",
            fake_object_decoder,
            raising=False,
        )

        monkeypatch.setattr(
            "prefect.serializers.prefect_json_object_decoder",
            prefect_object_decoder,
        )

        serializer = JSONSerializer(
            object_decoder="prefect.serializers.fake_object_decoder"
        )

        # Decoder hooks are only called for dicts
        assert serializer.loads(json.dumps({"foo": "bar"}).encode()) == "test"
        fake_object_decoder.assert_called_once_with({"foo": "bar"})
        prefect_object_decoder.assert_not_called()

    def test_allows_custom_kwargs(self, monkeypatch):
        dumps_mock = MagicMock()
        loads_mock = MagicMock()
        monkeypatch.setattr("json.dumps", dumps_mock)
        monkeypatch.setattr("json.loads", loads_mock)
        serializer = JSONSerializer(
            dumps_kwargs={"foo": "bar"}, loads_kwargs={"bar": "foo"}
        )
        serializer.dumps("test")
        serializer.loads(b"test")
        dumps_mock.assert_called_once_with(
            "test", default=prefect_json_object_encoder, foo="bar"
        )
        loads_mock.assert_called_once_with(
            "test", object_hook=prefect_json_object_decoder, bar="foo"
        )

    def test_does_not_allow_object_hook_collision(self):
        with pytest.raises(ValidationError):
            JSONSerializer(loads_kwargs={"object_hook": "foo"})

    def test_does_not_allow_default_collision(self):
        with pytest.raises(ValidationError):
            JSONSerializer(dumps_kwargs={"default": "foo"})


class TestCompressedSerializer:
    @pytest.mark.parametrize("data", SERIALIZER_TEST_CASES)
    def test_simple_roundtrip(self, data):
        serializer = CompressedSerializer(serializer="pickle")
        serialized = serializer.dumps(data)
        assert serializer.loads(serialized) == data

    @pytest.mark.parametrize("lib", ["bz2", "lzma", "zlib"])
    def test_allows_stdlib_compression_libraries(self, lib):
        serializer = CompressedSerializer(compressionlib=lib, serializer="pickle")
        serialized = serializer.dumps("test")
        assert serializer.loads(serialized) == "test"

    def test_uses_alternative_compression_library(self, monkeypatch):
        compress_mock = MagicMock(return_value=b"test")
        decompress_mock = MagicMock(return_value=PickleSerializer().dumps("test"))
        monkeypatch.setattr("zlib.compress", compress_mock)
        monkeypatch.setattr("zlib.decompress", decompress_mock)
        serializer = CompressedSerializer(compressionlib="zlib", serializer="pickle")
        serializer.dumps("test")
        serializer.loads(b"test")
        compress_mock.assert_called_once()
        decompress_mock.assert_called_once()

    def test_uses_given_serializer(self, monkeypatch):
        compress_mock = MagicMock(return_value=b"test")
        decompress_mock = MagicMock(return_value=JSONSerializer().dumps("test"))
        monkeypatch.setattr("zlib.compress", compress_mock)
        monkeypatch.setattr("zlib.decompress", decompress_mock)
        serializer = CompressedSerializer(compressionlib="zlib", serializer="json")
        serializer.dumps("test")
        serializer.loads(b"test")
        compress_mock.assert_called_once()
        decompress_mock.assert_called_once()

    def test_pickle_shorthand(self):
        serializer = Serializer(type="compressed/pickle")
        assert isinstance(serializer, CompressedSerializer)
        assert isinstance(serializer.serializer, PickleSerializer)

    def test_json_shorthand(self):
        serializer = Serializer(type="compressed/json")
        assert isinstance(serializer, CompressedSerializer)
        assert isinstance(serializer.serializer, JSONSerializer)
