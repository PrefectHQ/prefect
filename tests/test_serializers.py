import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pydantic
import pytest

from prefect.serializers import (
    JSONSerializer,
    PickleSerializer,
    Serializer,
    prefect_json_object_decoder,
    prefect_json_object_encoder,
)
from prefect.utilities.dispatch import get_registry_for_type

# Freeze a UUID for deterministic tests
TEST_UUID = uuid.UUID("a53e3495-d681-4a53-84b8-9d9542f7237c")


class MyModel(pydantic.BaseModel):
    x: int
    y: uuid.UUID


@dataclass
class MyDataclass:
    x: int
    y: str


# Simple test cases that all serializers should support roundtrips for
SERIALIZER_TEST_CASES = [
    1,
    "test",
    {"foo": "bar"},
    ["x", "y"],
    TEST_UUID,
    MyModel(x=1, y=TEST_UUID),
    MyDataclass(x=1, y="test"),
]


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
            type = "foo"

            def dumps(self, obj):
                pass

            def loads(self, obj):
                pass

        with pytest.raises(pydantic.ValidationError):
            Foo(x="test")

    def test_serializers_can_be_created_by_dict(self):
        class Foo(pydantic.BaseModel):
            serializer: Serializer

        class Bar(Serializer):
            type = "bar"

            def dumps(self, obj):
                pass

            def loads(self, obj):
                pass

        model = Foo(serializer={"type": "bar"})
        assert isinstance(model.serializer, Bar)

    def test_serializers_can_be_created_by_object(self):
        class Foo(pydantic.BaseModel):
            serializer: Serializer

        class Bar(Serializer):
            type = "bar"

            def dumps(self, obj):
                pass

            def loads(self, obj):
                pass

        model = Foo(serializer=Bar())
        assert isinstance(model.serializer, Bar)

    def test_serializers_can_be_created_by_type_string(self):
        class Foo(pydantic.BaseModel):
            serializer: Serializer

            @pydantic.validator("serializer", pre=True)
            def cast_type_to_dict(cls, value):
                if isinstance(value, str):
                    return {"type": value}
                return value

        class Bar(Serializer):
            type = "bar"

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

    def test_does_not_allow_pickle_modules_without_cloudpickle(self):
        with pytest.raises(ValueError, match="cloudpickle"):
            PickleSerializer(pickle_modules=["test"], picklelib="pickle")

    def test_supports_module_serialization(self, monkeypatch):
        monkeypatch.syspath_prepend(
            str(Path(__file__).parent / "test-projects" / "import-project")
        )

        from my_module.flow import test_flow

        serializer = PickleSerializer(pickle_modules=["my_module"])
        content = serializer.dumps(test_flow)

        monkeypatch.undo()
        sys.modules.pop("my_module")

        flow = serializer.loads(content)
        assert flow() == "test!"

    def test_fails_on_relative_import_without_module_serialization(
        self,
        monkeypatch,
    ):
        monkeypatch.syspath_prepend(
            str(Path(__file__).parent / "test-projects" / "import-project")
        )

        from my_module.flow import test_flow

        serializer = PickleSerializer()
        content = serializer.dumps(test_flow)

        monkeypatch.undo()
        sys.modules.pop("my_module")

        with pytest.raises(ModuleNotFoundError, match="No module named 'my_module'"):
            serializer.loads(content)


class TestJSONSerializer:
    @pytest.mark.parametrize("data", SERIALIZER_TEST_CASES)
    def test_simple_roundtrip(self, data):
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
            "prefect.fake_object_encoder", fake_object_encoder, raising=False
        )
        monkeypatch.setattr(
            "prefect.serializers.prefect_json_object_encoder",
            prefect_object_encoder,
        )

        serializer = JSONSerializer(object_encoder="prefect.fake_object_encoder")

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
            "prefect.fake_object_decoder", fake_object_decoder, raising=False
        )

        monkeypatch.setattr(
            "prefect.serializers.prefect_json_object_decoder",
            prefect_object_decoder,
        )

        serializer = JSONSerializer(object_decoder="prefect.fake_object_decoder")

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
        with pytest.raises(pydantic.ValidationError):
            JSONSerializer(loads_kwargs={"object_hook": "foo"})

    def test_does_not_allow_default_collision(self):
        with pytest.raises(pydantic.ValidationError):
            JSONSerializer(dumps_kwargs={"default": "foo"})
