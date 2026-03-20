from importlib import import_module
from types import ModuleType

from prefect.cli._app import app

__all__ = ["app"]


def __getattr__(name: str) -> ModuleType:
    # Preserve historical attribute-style access such as `prefect.cli.dev`
    # without reintroducing eager imports at package import time.
    module_name = f"{__name__}.{name}"
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None

    globals()[name] = module
    return module
