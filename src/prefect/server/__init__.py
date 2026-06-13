from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prefect.server import models, orchestration, schemas, services

__all__ = ["models", "orchestration", "schemas", "services"]


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
