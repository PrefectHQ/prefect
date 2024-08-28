# isort: skip_file

# Setup version and path constants

from . import _version
import importlib
import pathlib
from typing import TYPE_CHECKING, Any

__version_info__ = _version.get_versions()
__version__ = __version_info__["version"]

# The absolute path to this module
__module_path__ = pathlib.Path(__file__).parent
# The absolute path to the root of the repository, only valid for use during development
__development_base_path__ = __module_path__.parents[1]

# The absolute path to the built UI within the Python module, used by
# `prefect server start` to serve a dynamic build of the UI
__ui_static_subpath__ = __module_path__ / "server" / "ui_build"

# The absolute path to the built UI within the Python module
__ui_static_path__ = __module_path__ / "server" / "ui"

del _version, pathlib

if TYPE_CHECKING:
    from .main import (
        allow_failure,
        flow,
        Flow,
        get_client,
        get_run_logger,
        State,
        tags,
        task,
        Task,
        Transaction,
        unmapped,
        serve,
        deploy,
        pause_flow_run,
        resume_flow_run,
        suspend_flow_run,
    )

_slots: dict[str, Any] = {
    "__version_info__": __version_info__,
    "__version__": __version__,
    "__module_path__": __module_path__,
    "__development_base_path__": __development_base_path__,
    "__ui_static_subpath__": __ui_static_subpath__,
    "__ui_static_path__": __ui_static_path__,
}

_public_api: dict[str, tuple[str, str]] = {
    "allow_failure": (__spec__.parent, ".main"),
    "flow": (__spec__.parent, ".main"),
    "Flow": (__spec__.parent, ".main"),
    "get_client": (__spec__.parent, ".main"),
    "get_run_logger": (__spec__.parent, ".main"),
    "State": (__spec__.parent, ".main"),
    "tags": (__spec__.parent, ".main"),
    "task": (__spec__.parent, ".main"),
    "Task": (__spec__.parent, ".main"),
    "Transaction": (__spec__.parent, ".main"),
    "unmapped": (__spec__.parent, ".main"),
    "serve": (__spec__.parent, ".main"),
    "deploy": (__spec__.parent, ".main"),
    "pause_flow_run": (__spec__.parent, ".main"),
    "resume_flow_run": (__spec__.parent, ".main"),
    "suspend_flow_run": (__spec__.parent, ".main"),
}

# Declare API for type-checkers
__all__ = [
    "allow_failure",
    "flow",
    "Flow",
    "get_client",
    "get_run_logger",
    "State",
    "tags",
    "task",
    "Task",
    "Transaction",
    "unmapped",
    "serve",
    "deploy",
    "pause_flow_run",
    "resume_flow_run",
    "suspend_flow_run",
    "__version_info__",
    "__version__",
    "__module_path__",
    "__development_base_path__",
    "__ui_static_subpath__",
    "__ui_static_path__",
]


def __getattr__(attr_name: str) -> object:
    if attr_name in _slots:
        return _slots[attr_name]

    dynamic_attr = _public_api.get(attr_name)
    if dynamic_attr is None:
        return importlib.import_module(f".{attr_name}", package=__name__)

    package, module_name = dynamic_attr

    from importlib import import_module

    if module_name == "__module__":
        return import_module(f".{attr_name}", package=package)
    else:
        module = import_module(module_name, package=package)
        return getattr(module, attr_name)
