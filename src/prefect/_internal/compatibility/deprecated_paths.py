"""
Generic helper for keeping a deprecated module path working as a re-export
of a new location, emitting a DeprecationWarning per attribute access.

Independent of any specific Prefect version migration. Intended for cases
where a feature graduates between lifecycle stages (e.g., experimental to
GA) and we want the old import path to continue working with a clear hand
off message, but without coupling to the v2->v3 module migration helpers
in `prefect._internal.compatibility.migration`.
"""

from __future__ import annotations

import warnings
from typing import Any, Callable, Iterable

from pydantic._internal._validators import import_string


def deprecated_module_attrs(
    old_module: str,
    new_module: str,
    names: Iterable[str],
) -> Callable[[str], Any]:
    """
    Build a `__getattr__` for a deprecated module that re-exports public
    symbols from a new location. Each access emits a DeprecationWarning
    pointing the user at the new path.

    Symbols not in `names` raise `AttributeError` (rather than being
    silently re-exported) — this keeps the public surface explicit and
    avoids leaking implementation details that the new location does not
    intend to expose.

    Usage at the bottom of the deprecated module:

        from prefect._internal.compatibility.deprecated_paths import (
            deprecated_module_attrs,
        )

        __getattr__ = deprecated_module_attrs(
            __name__,
            "prefect.plugins",
            ("register_hook", "HookContext"),
        )
    """
    name_set = frozenset(names)

    def __getattr__(name: str) -> Any:
        if name in name_set:
            warnings.warn(
                f"`{old_module}.{name}` has moved to `{new_module}.{name}`. "
                f"Update your imports; the old path will be removed in a "
                f"future release.",
                DeprecationWarning,
                stacklevel=2,
            )
            return import_string(f"{new_module}:{name}")
        raise AttributeError(f"module {old_module!r} has no attribute {name!r}")

    return __getattr__
