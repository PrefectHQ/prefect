import base64
import io
import json
import subprocess
import uuid
from dataclasses import dataclass
from typing import Any, Generic, TypeVar
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
from prefect.utilities.importtools import to_qualified_name

# Freeze a UUID for deterministic tests
TEST_UUID = uuid.UUID("a53e3495-d681-4a53-84b8-9d9542f7237c")


class MyModel(BaseModel):
    x: int
    y: uuid.UUID


T = TypeVar("T")


class GenericResult(BaseModel, Generic[T]):
    """Generic model for testing JSON serialization of parameterized types."""

    data: T | None = None
    message: str = ""


@dataclass
class MyDataclass:
    x: int
    y: str


@dataclass
class GenericDataclass(Generic[T]):
    """Generic dataclass for testing non-Pydantic generic serialization."""

    data: T


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
EXCEPTION_TEST_CASES = [
    Exception("foo"),
    ValueError("bar"),
    subprocess.CalledProcessError(1, "ls -l"),
    subprocess.CalledProcessError(2, ["ls", "-l"]),
]


class NarrowerConstructor(Exception):
    """An exception whose `args` hold more than its constructor accepts."""

    def __init__(self, message: str):
        super().__init__(message, "context the constructor does not take")


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

    def test_unknown_serializers_raise_validation_error(self):
        with pytest.raises(ValidationError, match="type"):
            Serializer(type="a-custom-serializer", foo="bar")


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

    def test_picklelib_is_used(self, monkeypatch: pytest.MonkeyPatch):
        dumps = MagicMock(return_value=b"test")
        loads = MagicMock(return_value="test")
        monkeypatch.setattr("pickle.dumps", dumps)
        monkeypatch.setattr("pickle.loads", loads)
        serializer = PickleSerializer(picklelib="pickle")
        serializer.dumps("test")
        dumps.assert_called_once_with("test")
        serializer.loads(b"test")
        loads.assert_called_once_with(base64.decodebytes(b"test"))

    def test_picklelib_must_implement_dumps(self, monkeypatch: pytest.MonkeyPatch):
        import pickle

        monkeypatch.delattr(pickle, "dumps")
        with pytest.raises(
            ValueError,
            match="Pickle library at 'pickle' does not have a 'dumps' method.",
        ):
            PickleSerializer(picklelib="pickle")

    def test_picklelib_must_implement_loads(self, monkeypatch: pytest.MonkeyPatch):
        import pickle

        monkeypatch.delattr(pickle, "loads")
        with pytest.raises(
            ValueError,
            match="Pickle library at 'pickle' does not have a 'loads' method.",
        ):
            PickleSerializer(picklelib="pickle")


class TestJSONSerializer:
    @pytest.mark.parametrize("data", SERIALIZER_TEST_CASES)
    def test_simple_roundtrip(self, data: Any):
        serializer = JSONSerializer()
        serialized = serializer.dumps(data)
        assert serializer.loads(serialized) == data

    @pytest.mark.parametrize("data", EXCEPTION_TEST_CASES)
    def test_exception_roundtrip(self, data: Any):
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
    def test_simple_roundtrip_with_complex_bytes(self, data: Any):
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

    def test_uses_alternative_json_library(self, monkeypatch: pytest.MonkeyPatch):
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

    def test_json_serializer_does_not_consume_iobase_objects(self):
        serializer = JSONSerializer()
        string_io_content = "hello world from unit test"
        string_io = io.StringIO(string_io_content)
        data_with_stream = {"my_stream": string_io, "other_data": 123}

        string_io.seek(0)
        assert string_io.tell() == 0, "Initial seek(0) failed"

        serialized_data = serializer.dumps(data_with_stream)

        assert string_io.tell() == 0, "Stream pointer moved after dumps()"
        assert string_io.read() == string_io_content, (
            "Stream content changed or was consumed after dumps()"
        )
        string_io.seek(0)

        deserialized_data = json.loads(serialized_data.decode())

        deserialized_stream_placeholder: dict[str, Any] = deserialized_data.get(
            "my_stream"
        )

        assert isinstance(deserialized_stream_placeholder, dict), (
            f"Deserialized 'my_stream' should be a dict placeholder, "
            f"but got {type(deserialized_stream_placeholder)}"
        )

        assert deserialized_stream_placeholder.get("__class__") == to_qualified_name(
            io.StringIO
        ), (
            f"Placeholder __class__ ('{deserialized_stream_placeholder.get('__class__')}') "
            f"does not match expected ('{to_qualified_name(io.StringIO)}')"
        )

        placeholder_data_string = deserialized_stream_placeholder.get("data")
        assert isinstance(placeholder_data_string, str), (
            f"Placeholder data field should be a string, "
            f"but got {type(placeholder_data_string)}"
        )

        expected_placeholder_prefix = "<Prefect IOStream Placeholder:"
        expected_placeholder_type_info = f"type={string_io.__class__.__name__}"
        expected_placeholder_repr_info = f"repr={repr(string_io)}"
        expected_placeholder_suffix = "(original content not read)>"

        assert expected_placeholder_prefix in placeholder_data_string, (
            f"Placeholder prefix '{expected_placeholder_prefix}' missing in placeholder string: {placeholder_data_string}"
        )
        assert expected_placeholder_type_info in placeholder_data_string, (
            f"Expected type info '{expected_placeholder_type_info}' not in placeholder string: {placeholder_data_string}"
        )
        assert expected_placeholder_repr_info in placeholder_data_string, (
            f"Expected repr info '{expected_placeholder_repr_info}' not in placeholder string: {placeholder_data_string}"
        )
        assert expected_placeholder_suffix in placeholder_data_string, (
            f"Placeholder suffix '{expected_placeholder_suffix}' missing in placeholder string: {placeholder_data_string}"
        )

        assert deserialized_data.get("other_data") == 123, "Other data was altered"

    def test_allows_custom_encoder(self, monkeypatch: pytest.MonkeyPatch):
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

    def test_allows_custom_decoder(self, monkeypatch: pytest.MonkeyPatch):
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

    def test_allows_custom_kwargs(self, monkeypatch: pytest.MonkeyPatch):
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

    def test_pydantic_generic_model_roundtrip(self):
        """Test that Pydantic generic models with type parameters can be serialized.

        Regression test for: https://github.com/PrefectHQ/prefect/issues/XXXX

        When using parameterized generics like `APIResult[str]`, the class name
        includes brackets which cannot be imported. The serializer should extract
        the origin class for proper roundtrip serialization.
        """
        serializer = JSONSerializer()

        # Test with concrete type parameter
        result = GenericResult[str](data="hello", message="success")
        serialized = serializer.dumps(result)

        # Verify the serialized class name doesn't include type parameters
        decoded = json.loads(serialized)
        assert "[" not in decoded["__class__"], (
            f"Class name should not contain brackets: {decoded['__class__']}"
        )

        # Verify roundtrip works
        loaded = serializer.loads(serialized)
        assert loaded.data == "hello"
        assert loaded.message == "success"

    def test_dataclass_generic_model_roundtrip(self):
        """Test that non-Pydantic generic models still work correctly.

        Ensures the fix for Pydantic generics doesn't break standard
        Generic dataclasses, which don't have the bracketed name issue.
        """
        serializer = JSONSerializer()

        # Non-Pydantic generics don't create distinct classes per parameterization
        result = GenericDataclass[str](data="hello")
        serialized = serializer.dumps(result)

        # Verify roundtrip works
        loaded = serializer.loads(serialized)
        assert loaded.data == "hello"


class TestJSONObjectDecoderSecurity:
    def test_exc_type_rejects_non_exception_class(self):
        with pytest.raises(ValueError, match="Invalid exception type"):
            prefect_json_object_decoder(
                {"__exc_type__": "builtins.int", "message": "42"}
            )

    def test_exc_type_allows_real_exception(self):
        result = prefect_json_object_decoder(
            {"__exc_type__": "builtins.ValueError", "message": "test error"}
        )
        assert isinstance(result, ValueError)
        assert str(result) == "test error"

    def test_exc_type_raises_on_unimportable_class(self):
        with pytest.raises(ValueError, match="Invalid exception type"):
            prefect_json_object_decoder(
                {"__exc_type__": "nonexistent.FakeError", "message": "test"}
            )

    def test_exc_type_raises_on_dotless_name(self):
        with pytest.raises(ValueError, match="Invalid exception type"):
            prefect_json_object_decoder({"__exc_type__": "int", "message": "test"})

    def test_class_path_handles_unimportable_class(self):
        result = prefect_json_object_decoder(
            {"__class__": "nonexistent.Module", "data": {}}
        )
        assert result == {"__class__": "nonexistent.Module", "data": {}}

    def test_class_path_handles_dotless_name(self):
        result = prefect_json_object_decoder({"__class__": "int", "data": {}})
        assert result == {"__class__": "int", "data": {}}


class TestJSONExceptionArguments:
    def test_multi_argument_exception_keeps_its_arguments(self):
        serializer = JSONSerializer()
        loaded = serializer.loads(
            serializer.dumps(subprocess.CalledProcessError(1, "ls -l"))
        )
        assert isinstance(loaded, subprocess.CalledProcessError)
        assert loaded.returncode == 1
        assert loaded.cmd == "ls -l"

    def test_argument_types_survive_the_roundtrip(self):
        serializer = JSONSerializer()
        loaded = serializer.loads(serializer.dumps(ValueError(42)))
        assert loaded.args == (42,)

    def test_container_arguments_are_carried(self):
        serializer = JSONSerializer()
        payload = {"code": 42, "detail": ["a", "b"]}
        loaded = serializer.loads(serializer.dumps(Exception(payload)))
        assert loaded.args == (payload,)

    def test_arguments_that_are_not_json_native_are_omitted(self):
        exc = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        serializer = JSONSerializer()

        blob = serializer.dumps(exc)

        assert "__exc_args__" not in json.loads(blob)
        # Without its arguments, reconstruction stays where it was before.
        with pytest.raises(TypeError):
            serializer.loads(blob)

    def test_payload_without_arguments_still_decodes(self):
        result = prefect_json_object_decoder(
            {"__exc_type__": "builtins.ValueError", "message": "bar"}
        )
        assert exceptions_equal(result, ValueError("bar"))

    def test_arguments_the_constructor_rejects_fall_back_to_the_message(self):
        serializer = JSONSerializer()
        loaded = serializer.loads(serializer.dumps(NarrowerConstructor("boom")))
        assert isinstance(loaded, NarrowerConstructor)

    def test_self_referential_list_argument_is_omitted(self):
        values: list[Any] = []
        values.append(values)
        serializer = JSONSerializer()

        blob = serializer.dumps(Exception(values))

        assert "__exc_args__" not in json.loads(blob)
        assert serializer.loads(blob).args == ("[[...]]",)

    def test_self_referential_dict_argument_is_omitted(self):
        payload: dict[str, Any] = {}
        payload["self"] = payload
        serializer = JSONSerializer()

        blob = serializer.dumps(Exception(payload))

        assert "__exc_args__" not in json.loads(blob)

    def test_repeated_sibling_container_is_still_carried(self):
        shared = ["a"]
        serializer = JSONSerializer()

        loaded = serializer.loads(serializer.dumps(Exception([shared, shared])))

        assert loaded.args == ([["a"], ["a"]],)

    def test_tuple_argument_is_omitted(self):
        serializer = JSONSerializer()

        blob = serializer.dumps(KeyError((1, 2)))

        assert "__exc_args__" not in json.loads(blob)
        # A tuple comes back from JSON as a list, which is not the same key.
        assert serializer.loads(blob).args == ("(1, 2)",)

    @pytest.mark.parametrize("marker", ["__class__", "__exc_type__"])
    def test_argument_dict_holding_a_decoder_marker_is_omitted(self, marker: str):
        serializer = JSONSerializer()

        blob = serializer.dumps(Exception({marker: "builtins.int", "data": 8}))

        assert "__exc_args__" not in json.loads(blob)

    def test_nested_argument_dict_holding_a_decoder_marker_is_omitted(self):
        serializer = JSONSerializer()

        blob = serializer.dumps(
            Exception(["x", {"__class__": "builtins.int", "data": 8}])
        )

        assert "__exc_args__" not in json.loads(blob)

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_float_argument_is_omitted(self, value: float):
        serializer = JSONSerializer(dumps_kwargs={"allow_nan": False})

        blob = serializer.dumps(ValueError(value))

        assert "__exc_args__" not in json.loads(blob)


class TestCompressedSerializer:
    @pytest.mark.parametrize("data", SERIALIZER_TEST_CASES)
    def test_simple_roundtrip(self, data: Any):
        serializer = CompressedSerializer(serializer="pickle")
        serialized = serializer.dumps(data)
        assert serializer.loads(serialized) == data

    @pytest.mark.parametrize("lib", ["bz2", "lzma", "zlib"])
    def test_allows_stdlib_compression_libraries(self, lib):
        serializer = CompressedSerializer(compressionlib=lib, serializer="pickle")
        serialized = serializer.dumps("test")
        assert serializer.loads(serialized) == "test"

    def test_uses_alternative_compression_library(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        compress_mock = MagicMock(return_value=b"test")
        decompress_mock = MagicMock(return_value=PickleSerializer().dumps("test"))
        monkeypatch.setattr("zlib.compress", compress_mock)
        monkeypatch.setattr("zlib.decompress", decompress_mock)
        serializer = CompressedSerializer(compressionlib="zlib", serializer="pickle")
        serializer.dumps("test")
        serializer.loads(b"test")
        compress_mock.assert_called_once()
        decompress_mock.assert_called_once()

    def test_uses_given_serializer(self, monkeypatch: pytest.MonkeyPatch):
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
