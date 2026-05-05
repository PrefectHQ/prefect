"""
Prefect plugin system.

Provides startup hooks that allow third-party packages to run initialization
code (e.g., set environment variables, configure DB connections) before
Prefect CLI commands, workers, or scripts begin work, plus loaders for the
`prefect.collections` entry point group used by Prefect collection packages.

This module is the stable public surface for the plugin system. Implementation
modules live under `prefect._internal.plugins.*` and may change without notice.

The collection-loader symbols are imported eagerly because they have no extra
dependencies; the pluggy-backed hook system symbols are loaded lazily via
`__getattr__` so that minimal builds (e.g. `prefect-client`) which do not
ship `pluggy` can still `from prefect.plugins import load_prefect_collections`
without a hard ImportError at module load time.
"""

from typing import TYPE_CHECKING, Any

from prefect._internal.plugins.collections import (
    load_prefect_collections,
    safe_load_entrypoints,
)

if TYPE_CHECKING:
    from pluggy import HookimplMarker as _HookimplMarker

    from prefect._internal.plugins.diagnostics import SetupSummary
    from prefect._internal.plugins.spec import (
        PREFECT_PLUGIN_API_VERSION,
        HookContext,
        HookSpec,
        SetupResult,
    )
    from prefect._internal.plugins.startup import run_startup_hooks

    register_hook: _HookimplMarker

__all__ = [
    "load_prefect_collections",
    "safe_load_entrypoints",
    "run_startup_hooks",
    "HookContext",
    "SetupResult",
    "HookSpec",
    "SetupSummary",
    "PREFECT_PLUGIN_API_VERSION",
    "register_hook",
]


_LAZY_HOOK_ATTRS = {
    "register_hook": ("prefect._internal.plugins.manager", "register_hook"),
    "run_startup_hooks": ("prefect._internal.plugins.startup", "run_startup_hooks"),
    "HookContext": ("prefect._internal.plugins.spec", "HookContext"),
    "HookSpec": ("prefect._internal.plugins.spec", "HookSpec"),
    "SetupResult": ("prefect._internal.plugins.spec", "SetupResult"),
    "PREFECT_PLUGIN_API_VERSION": (
        "prefect._internal.plugins.spec",
        "PREFECT_PLUGIN_API_VERSION",
    ),
    "SetupSummary": ("prefect._internal.plugins.diagnostics", "SetupSummary"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_HOOK_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module 'prefect.plugins' has no attribute {name!r}")
    import importlib

    module = importlib.import_module(target[0])
    value = getattr(module, target[1])
    globals()[name] = value
    return value
