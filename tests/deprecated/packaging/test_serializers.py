import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Generator

import pytest

from prefect.deprecated.packaging.serializers import (
    ImportSerializer,
    PickleSerializer,
    SourceSerializer,
)


def foo(return_val="foo"):
    return return_val


@pytest.mark.parametrize(
    "Serializer", [SourceSerializer, ImportSerializer, PickleSerializer]
)
def test_serialize_function(Serializer):
    serializer = Serializer()
    blob = serializer.dumps(foo)
    result = serializer.loads(blob)

    assert type(result) == type(foo)
    assert result.__kwdefaults__ == foo.__kwdefaults__
    assert result.__name__ == foo.__name__

    # The source serializer updates the module to __prefect_loader__
    if not isinstance(serializer, SourceSerializer):
        assert result.__module__ == result.__module__

    assert result() == foo(), "Result should be callable"


@pytest.fixture
def busted_pickler() -> Generator[ModuleType, None, None]:
    spec = importlib.machinery.ModuleSpec("busted_pickle", None)
    busted_pickler = importlib.util.module_from_spec(spec)
    sys.modules["busted_pickler"] = busted_pickler

    try:
        yield busted_pickler
    finally:
        del sys.modules["busted_pickler"]


def test_pickle_serializer_needs_a_sane_pickler(busted_pickler: ModuleType):
    with pytest.raises(ValueError, match="Failed to import requested pickle library"):
        PickleSerializer(picklelib="not-even-valid-identifier")

    with pytest.raises(ValueError, match="does not have a 'dumps'"):
        PickleSerializer(picklelib="busted_pickler")

    setattr(busted_pickler, "dumps", lambda: "wat")

    with pytest.raises(ValueError, match="does not have a 'loads'"):
        PickleSerializer(picklelib="busted_pickler")

    setattr(busted_pickler, "loads", lambda: "wat")

    serializer = PickleSerializer(picklelib="busted_pickler")
    assert serializer.picklelib == "busted_pickler"


def test_pickle_serializer_warns_about_mismatched_versions():
    import cloudpickle

    assert cloudpickle.__version__ != "0.0.0.0.0.0"
    with pytest.warns(RuntimeWarning, match="Mismatched 'cloudpickle' versions"):
        PickleSerializer(picklelib="cloudpickle", picklelib_version="0.0.0.0.0.0")

    PickleSerializer(picklelib="cloudpickle", picklelib_version=cloudpickle.__version__)


def test_source_serializer_must_find_module():
    with pytest.raises(ValueError, match="Cannot determine source module for object"):
        # object a C object that doesn't have a __module__
        SourceSerializer().dumps(object())


def test_source_serializer_needs_a_file_module():
    with pytest.raises(ValueError, match="Found module <module 'builtins'"):
        # object comes from the module `builtins`, a C module without Python source
        SourceSerializer().dumps(object)


@pytest.mark.parametrize(
    "garbage",
    [
        b"{}",
        b"[]",
        b"null",
        b'{"source": "import antigravity\\n"}',
    ],
)
def test_source_serializer_cannot_decode_just_any_old_thing(garbage: bytes):
    with pytest.raises(ValueError, match="Invalid serialized data"):
        SourceSerializer().loads(garbage)


def test_pickle_serializer_does_not_allow_pickle_modules_without_cloudpickle():
    with pytest.raises(ValueError, match="cloudpickle"):
        PickleSerializer(pickle_modules=["test"], picklelib="pickle")


def test_pickle_serializer_supports_module_serialization(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parent / "examples"))

    from my_module.flow import test_flow

    serializer = PickleSerializer(pickle_modules=["my_module"])
    content = serializer.dumps(test_flow)

    monkeypatch.undo()
    sys.modules.pop("my_module")

    flow = serializer.loads(content)
    assert flow() == "test!"


def test_pickle_serializer_fails_on_relative_import_without_module_serialization(
    monkeypatch,
):
    monkeypatch.syspath_prepend(str(Path(__file__).parent / "examples"))

    from my_module.flow import test_flow

    serializer = PickleSerializer()
    content = serializer.dumps(test_flow)

    monkeypatch.undo()
    sys.modules.pop("my_module")

    with pytest.raises(ModuleNotFoundError, match="No module named 'my_module'"):
        serializer.loads(content)
