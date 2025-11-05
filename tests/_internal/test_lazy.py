from __future__ import annotations

import pytest

from prefect._internal.lazy import LazyDict


def test_lazy_dict_defers_loading():
    """LazyDict should not call loader function on initialization."""
    call_count = 0

    def loader() -> dict[str, int]:
        nonlocal call_count
        call_count += 1
        return {"a": 1, "b": 2}

    _lazy = LazyDict(loader)
    assert call_count == 0, "Loader should not be called on initialization"


def test_lazy_dict_loads_on_first_access():
    """LazyDict should call loader function on first access."""
    call_count = 0

    def loader() -> dict[str, int]:
        nonlocal call_count
        call_count += 1
        return {"a": 1, "b": 2}

    lazy = LazyDict(loader)
    result = lazy.get("a")

    assert call_count == 1, "Loader should be called on first access"
    assert result == 1


def test_lazy_dict_caches_result():
    """LazyDict should only call loader once and cache the result."""
    call_count = 0

    def loader() -> dict[str, int]:
        nonlocal call_count
        call_count += 1
        return {"a": 1, "b": 2}

    lazy = LazyDict(loader)

    # Multiple accesses
    lazy.get("a")
    lazy.get("b")
    "a" in lazy
    lazy["b"]

    assert call_count == 1, "Loader should only be called once"


def test_lazy_dict_get_with_default():
    """LazyDict.get() should support default values."""

    def loader() -> dict[str, int]:
        return {"a": 1}

    lazy = LazyDict(loader)

    assert lazy.get("a") == 1
    assert lazy.get("missing") is None
    assert lazy.get("missing", 42) == 42


def test_lazy_dict_contains():
    """LazyDict should support 'in' operator."""

    def loader() -> dict[str, int]:
        return {"a": 1, "b": 2}

    lazy = LazyDict(loader)

    assert "a" in lazy
    assert "b" in lazy
    assert "c" not in lazy


def test_lazy_dict_getitem():
    """LazyDict should support bracket notation."""

    def loader() -> dict[str, int]:
        return {"a": 1, "b": 2}

    lazy = LazyDict(loader)

    assert lazy["a"] == 1
    assert lazy["b"] == 2


def test_lazy_dict_getitem_raises_keyerror():
    """LazyDict should raise KeyError for missing keys with bracket notation."""

    def loader() -> dict[str, int]:
        return {"a": 1}

    lazy = LazyDict(loader)

    with pytest.raises(KeyError):
        _ = lazy["missing"]


def test_lazy_dict_with_complex_types():
    """LazyDict should work with complex value types."""

    class DummyClass:
        def __init__(self, value: int):
            self.value = value

    def loader() -> dict[str, DummyClass]:
        return {
            "obj1": DummyClass(10),
            "obj2": DummyClass(20),
        }

    lazy = LazyDict(loader)

    obj = lazy.get("obj1")
    assert obj is not None
    assert obj.value == 10


def test_lazy_dict_empty():
    """LazyDict should handle empty dictionaries."""

    def loader() -> dict[str, int]:
        return {}

    lazy = LazyDict(loader)

    assert lazy.get("any") is None
    assert "any" not in lazy
