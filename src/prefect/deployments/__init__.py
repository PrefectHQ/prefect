from typing import TYPE_CHECKING
from prefect._internal.compatibility.migration import getattr_migration


if TYPE_CHECKING:
    from .flow_runs import run_deployment
    from .base import initialize_project
    from .runner import deploy

_public_api: dict[str, tuple[str, str]] = {
    "initialize_project": (__spec__.parent, ".base"),
    "run_deployment": (__spec__.parent, ".flow_runs"),
    "deploy": (__spec__.parent, ".runner"),
}

# Declare API for type-checkers
__all__ = ["initialize_project", "deploy", "run_deployment"]


def __getattr__(attr_name: str) -> object:
    dynamic_attr = _public_api.get(attr_name)
    if dynamic_attr is None:
        return getattr_migration(__name__)(attr_name)

    package, module_name = dynamic_attr

    from importlib import import_module

    if module_name == "__module__":
        return import_module(f".{attr_name}", package=package)
    else:
        module = import_module(module_name, package=package)
        return getattr(module, attr_name)
