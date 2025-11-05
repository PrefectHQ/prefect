"""Utilities for lazy-loading module-level objects."""

from typing import Callable, Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class LazyDict(Generic[K, V]):
    """
    A dictionary-like object that defers loading its contents until first access.

    Useful for module-level registries that import heavy dependencies. The loader
    function is called once on first access, and the result is cached.

    Example:
        >>> def load_plugins() -> dict[str, type]:
        ...     from heavy_module import PluginA, PluginB
        ...     return {"a": PluginA, "b": PluginB}
        >>>
        >>> plugins: LazyDict[str, type] = LazyDict(load_plugins)
        >>> # Nothing loaded yet
        >>> plugins.get("a")  # Triggers load, returns PluginA
        >>> plugins.get("b")  # Uses cached result, returns PluginB
    """

    def __init__(self, loader_func: Callable[[], dict[K, V]]) -> None:
        self._loader = loader_func
        self._cache: dict[K, V] | None = None

    def _ensure_loaded(self) -> dict[K, V]:
        """Load the dictionary contents if not already loaded."""
        if self._cache is None:
            self._cache = self._loader()
        return self._cache

    def get(self, key: K, default: V | None = None) -> V | None:
        """Get an item from the lazy dict, loading if necessary."""
        return self._ensure_loaded().get(key, default)

    def __contains__(self, key: K) -> bool:
        """Check if key is in the lazy dict, loading if necessary."""
        return key in self._ensure_loaded()

    def __getitem__(self, key: K) -> V:
        """Get an item from the lazy dict, loading if necessary."""
        return self._ensure_loaded()[key]
