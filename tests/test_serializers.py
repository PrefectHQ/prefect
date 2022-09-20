import sys
from pathlib import Path
from uuid import UUID

import pydantic
import pytest

from prefect.serializers import JSONSerializer, PickleSerializer, Serializer
from prefect.utilities.dispatch import get_registry_for_type

# Freeze a UUID for deterministic tests
TEST_UUID = UUID("a53e3495-d681-4a53-84b8-9d9542f7237c")

# Simple test cases that all serializers should support roundtrips for
SIMPLE_CASES = [1, "test", {"foo": "bar"}, ["x", "y"], TEST_UUID]


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

        with pytest.raises(pydantic.ValidationError):
            Foo(x="test")

    def test_serializers_can_be_created_by_dict(self):
        class Foo(pydantic.BaseModel):
            serializer: Serializer

        class Bar(Serializer):
            type = "bar"

        model = Foo(serializer={"type": "bar"})
        assert isinstance(model.serializer, Bar)

    def test_serializers_can_be_created_by_object(self):
        class Foo(pydantic.BaseModel):
            serializer: Serializer

        class Bar(Serializer):
            type = "bar"

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

        model = Foo(serializer="bar")
        assert isinstance(model.serializer, Bar)


class TestPickleSerializer:
    @pytest.mark.parametrize("data", SIMPLE_CASES)
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
    @pytest.mark.parametrize("data", SIMPLE_CASES)
    def test_simple_roundtrip(self, data):
        serializer = JSONSerializer()
        serialized = serializer.dumps(data)
        assert serializer.loads(serialized) == data
