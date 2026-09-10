from __future__ import annotations

import inspect
from types import ModuleType
from typing import Any, Callable

from prefect.cache_policies import _stabilize
from prefect.utilities.hashing import hash_objects


def hash_task_source_context(fn: Callable[..., Any]) -> str | None:
    """Hash captured values that supplement a task's source identity."""

    def value_hash(value: Any) -> str | None:
        if isinstance(value, ModuleType) or inspect.isclass(value) or callable(value):
            return None
        try:
            return hash_objects(_stabilize(value))
        except Exception:
            return None

    closure: list[tuple[str, str | None]] = []
    cells = getattr(fn, "__closure__", None) or ()
    names = getattr(getattr(fn, "__code__", None), "co_freevars", ())
    for name, cell in zip(names, cells):
        try:
            value = cell.cell_contents
        except ValueError:
            closure.append((name, None))
        else:
            closure.append((name, value_hash(value)))

    try:
        referenced_globals = inspect.getclosurevars(fn).globals
    except (TypeError, ValueError):
        referenced_globals = {}
    globals_ = sorted(
        (name, value_hash(value))
        for name, value in referenced_globals.items()
        if not isinstance(value, ModuleType)
        and not inspect.isclass(value)
        and not callable(value)
    )

    if not closure and not globals_:
        return None
    return hash_objects(("closure", closure), ("globals", globals_))
