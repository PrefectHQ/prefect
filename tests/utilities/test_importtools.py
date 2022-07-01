import importlib.util
from types import ModuleType

import pytest

import prefect
from prefect.utilities.importtools import (
    from_qualified_name,
    lazy_import,
    to_qualified_name,
)


def my_fn():
    pass


class Foo:
    pass


@pytest.mark.parametrize(
    "obj,expected",
    [
        (to_qualified_name, "prefect.utilities.importtools.to_qualified_name"),
        (prefect.tasks.Task, "prefect.tasks.Task"),
        (prefect.tasks.Task.__call__, "prefect.tasks.Task.__call__"),
        (lambda x: x + 1, "tests.utilities.test_importtools.<lambda>"),
        (my_fn, "tests.utilities.test_importtools.my_fn"),
    ],
)
def test_to_qualified_name(obj, expected):
    assert to_qualified_name(obj) == expected


@pytest.mark.parametrize("obj", [to_qualified_name, prefect.tasks.Task, my_fn, Foo])
def test_to_and_from_qualified_name_roundtrip(obj):
    assert from_qualified_name(to_qualified_name(obj)) == obj


def test_lazy_import():
    requests: ModuleType("requests") = lazy_import("requests")
    assert isinstance(requests, importlib.util._LazyModule)
    assert isinstance(requests, ModuleType)
    assert callable(requests.get)


def test_lazy_import_still_fails_for_missing_modules():
    with pytest.raises(ModuleNotFoundError, match="flibbidy"):
        lazy_import("flibbidy")
