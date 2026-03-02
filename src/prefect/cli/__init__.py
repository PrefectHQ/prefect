from importlib import import_module
from types import ModuleType

from prefect.cli._app import app

__all__ = ["app"]


def __getattr__(name: str) -> ModuleType:
    # Some internal tests and scripts access ``prefect.cli._prompts`` as an
    # attribute on the package. Preserve that behavior without eager imports.
    if name == "_prompts":
        module = import_module("prefect.cli._prompts")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
