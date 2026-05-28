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
    if name in __all__:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
