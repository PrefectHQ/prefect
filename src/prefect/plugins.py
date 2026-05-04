"""
Prefect plugin system.

Provides startup hooks that allow third-party packages to run initialization
code (e.g., set environment variables, configure DB connections) before
Prefect CLI commands, workers, or scripts begin work, plus loaders for the
`prefect.collections` entry point group used by Prefect collection packages.

This module is the stable public surface for the plugin system. Implementation
modules live under `prefect._internal.plugins.*` and may change without notice.
"""

from prefect._internal.plugins.collections import (
    load_prefect_collections,
    safe_load_entrypoints,
)
from prefect._internal.plugins.diagnostics import SetupSummary
from prefect._internal.plugins.manager import register_hook
from prefect._internal.plugins.spec import (
    PREFECT_PLUGIN_API_VERSION,
    HookContext,
    HookSpec,
    SetupResult,
)
from prefect._internal.plugins.startup import run_startup_hooks

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
