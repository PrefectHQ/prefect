from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .flow_runs import run_deployment
    from .base import initialize_project
    from .runner import deploy


_public_api: dict[str, tuple[str, str]] = {
    "initialize_project": (__spec__.parent, ".base"),
    "deploy": (__spec__.parent, ".runner"),
    "run_deployment": (__spec__.parent, ".flow_runs"),
}

# Declare API for type-checkers
__all__ = [
    "initialize_project",
    "deploy",
    "run_deployment",
]


def __getattr__(attr_name: str) -> object:
    from importlib import import_module

    dynamic_attr = _public_api.get(attr_name)
    if dynamic_attr is None:
        return import_module(f".{attr_name}", package=__name__)

    package, module_name = dynamic_attr

    if module_name == "__module__":
        return import_module(f".{attr_name}", package=package)
    else:
        module = import_module(module_name, package=package)
        return getattr(module, attr_name)
