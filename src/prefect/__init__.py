# isort: skip_file

# Setup version and path constants

import sys
from . import _build_info
import importlib
import pathlib
from typing import TYPE_CHECKING, Any, Optional, TypedDict, cast

if TYPE_CHECKING:
    from importlib.machinery import ModuleSpec
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
        aserve,
        pause_flow_run,
        resume_flow_run,
        suspend_flow_run,
    )
    from prefect.deployments.runner import deploy

    __spec__: ModuleSpec

    class VersionInfo(TypedDict("_FullRevisionId", {"full-revisionid": str})):
        version: str
        dirty: Optional[bool]
        error: Optional[str]
        date: Optional[str]


__version__ = _build_info.__version__
__version_info__: "VersionInfo" = cast(
    "VersionInfo",
    {
        "version": __version__,
        "date": _build_info.__build_date__,
        "full-revisionid": _build_info.__git_commit__,
        "error": None,
        "dirty": _build_info.__dirty__,
    },
)

# The absolute path to this module
__module_path__: pathlib.Path = pathlib.Path(__file__).parent
# The absolute path to the root of the repository, only valid for use during development
__development_base_path__: pathlib.Path = __module_path__.parents[1]

# The absolute path to the built UI within the Python module, used by
# `prefect server start` to serve a dynamic build of the UI
__ui_static_subpath__: pathlib.Path = __module_path__ / "server" / "ui_build"

# The absolute path to the built UI within the Python module
__ui_static_path__: pathlib.Path = __module_path__ / "server" / "ui"

del _build_info, pathlib

_public_api: dict[str, tuple[Optional[str], str]] = {
    "allow_failure": (__spec__.parent, ".main"),
    "aserve": (__spec__.parent, ".main"),
    "deploy": (__spec__.parent, ".deployments.runner"),
    "flow": (__spec__.parent, ".main"),
    "Flow": (__spec__.parent, ".main"),
    "get_client": (__spec__.parent, ".main"),
    "get_run_logger": (__spec__.parent, ".main"),
    "pause_flow_run": (__spec__.parent, ".main"),
    "resume_flow_run": (__spec__.parent, ".main"),
    "serve": (__spec__.parent, ".main"),
    "State": (__spec__.parent, ".main"),
    "suspend_flow_run": (__spec__.parent, ".main"),
    "tags": (__spec__.parent, ".main"),
    "task": (__spec__.parent, ".main"),
    "Task": (__spec__.parent, ".main"),
    "Transaction": (__spec__.parent, ".main"),
    "unmapped": (__spec__.parent, ".main"),
}

# Declare API for type-checkers
__all__ = [
    "__version__",
    "allow_failure",
    "aserve",
    "deploy",
    "flow",
    "Flow",
    "get_client",
    "get_run_logger",
    "pause_flow_run",
    "resume_flow_run",
    "serve",
    "State",
    "suspend_flow_run",
    "tags",
    "task",
    "Task",
    "Transaction",
    "unmapped",
]


def __getattr__(attr_name: str) -> Any:
    try:
        if (dynamic_attr := _public_api.get(attr_name)) is None:
            return importlib.import_module(f".{attr_name}", package=__name__)

        package, mname = dynamic_attr
        if mname == "__module__":
            return importlib.import_module(f".{attr_name}", package=package)
        else:
            module = importlib.import_module(mname, package=package)
            return getattr(module, attr_name)
    except ModuleNotFoundError as ex:
        mname, _, attr = (ex.name or "").rpartition(".")
        ctx = {"name": mname, "obj": attr} if sys.version_info >= (3, 10) else {}
        raise AttributeError(f"module {mname} has no attribute {attr}", **ctx) from ex
