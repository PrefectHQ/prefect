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
    assert call_count == 0


def test_lazy_dict_loads_once_and_caches():
    """LazyDict should call loader once on first access and cache result."""
    call_count = 0

    def loader() -> dict[str, int]:
        nonlocal call_count
        call_count += 1
        return {"a": 1, "b": 2}

    lazy = LazyDict(loader)

    # Multiple accesses using different methods
    assert lazy.get("a") == 1
    assert "b" in lazy
    assert lazy["b"] == 2

    # Loader should only be called once
    assert call_count == 1


@pytest.mark.parametrize(
    "key,default,expected",
    [
        ("a", None, 1),
        ("missing", None, None),
        ("missing", 42, 42),
    ],
)
def test_lazy_dict_get_with_default(key, default, expected):
    """LazyDict.get() should support default values."""
    lazy = LazyDict(lambda: {"a": 1})
    assert lazy.get(key, default) == expected


def test_lazy_dict_getitem_raises_keyerror():
    """LazyDict should raise KeyError for missing keys with bracket notation."""
    lazy = LazyDict(lambda: {"a": 1})

    with pytest.raises(KeyError):
        _ = lazy["missing"]
