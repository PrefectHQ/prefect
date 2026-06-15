from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prefect.server.schemas import (
        actions,
        core,
        filters,
        internal,
        responses,
        schedules,
        sorting,
        states,
        statuses,
        ui,
    )

__all__ = [
    "actions",
    "core",
    "filters",
    "internal",
    "responses",
    "schedules",
    "sorting",
    "states",
    "statuses",
    "ui",
]


def __getattr__(name: str) -> object:
    module_name = f"{__name__}.{name}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None

    globals()[name] = module
    return module
