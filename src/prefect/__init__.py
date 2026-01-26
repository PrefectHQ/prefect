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
        apause_flow_run,
        aresume_flow_run,
        aserve,
        asuspend_flow_run,
        flow,
        Flow,
        get_client,
        get_run_logger,
        pause_flow_run,
        resume_flow_run,
        serve,
        State,
        suspend_flow_run,
        tags,
        task,
        Task,
        Transaction,
        unmapped,
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

# The absolute path to the built V2 UI within the Python module, used by
# `prefect server start` to serve a dynamic build of the V2 UI
__ui_v2_static_subpath__: pathlib.Path = __module_path__ / "server" / "ui_v2_build"

# The absolute path to the built V2 UI within the Python module
__ui_v2_static_path__: pathlib.Path = __module_path__ / "server" / "ui-v2"

del _build_info, pathlib


def _initialize_plugins() -> None:
    """
    Initialize the experimental plugin system if enabled.

    This runs automatically when Prefect is imported and plugins are enabled
    via experiments.plugins.enabled setting. Errors are logged but don't prevent
    Prefect from loading.
    """
    try:
        # Import here to avoid circular imports and defer cost until needed
        from prefect.settings import get_current_settings

        if not get_current_settings().experiments.plugins.enabled:
            return

        import anyio

        from prefect._experimental.plugins import run_startup_hooks
        from prefect._experimental.plugins.spec import HookContext
        from prefect.context import refresh_global_settings_context
        from prefect.logging import get_logger
        from prefect.settings import get_current_settings

        ctx = HookContext(
            prefect_version=__version__,
            api_url=get_current_settings().api.url,
            logger_factory=get_logger,
        )

        # Run plugin hooks synchronously during import
        anyio.run(run_startup_hooks, ctx)

        # Refresh global settings context to pick up any env vars set by plugins
        refresh_global_settings_context()
    except SystemExit:
        # Re-raise SystemExit from strict mode
        raise
    except Exception as e:
        # Log but don't crash on plugin errors
        try:
            from prefect.logging import get_logger

            logger = get_logger("prefect.plugins")
            logger.exception("Failed to initialize plugins: %s", e)
        except Exception:
            # If even logging fails, print to stderr and continue
            import sys

            print(f"Failed to initialize plugins: {e}", file=sys.stderr)


# Initialize plugins on import if enabled
_initialize_plugins()

_public_api: dict[str, tuple[Optional[str], str]] = {
    "allow_failure": (__spec__.parent, ".main"),
    "apause_flow_run": (__spec__.parent, ".main"),
    "aresume_flow_run": (__spec__.parent, ".main"),
    "aserve": (__spec__.parent, ".main"),
    "asuspend_flow_run": (__spec__.parent, ".main"),
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
    "apause_flow_run",
    "aresume_flow_run",
    "aserve",
    "asuspend_flow_run",
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
