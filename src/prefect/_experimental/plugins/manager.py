"""
Plugin manager using pluggy with async bridge.
"""

from __future__ import annotations

import importlib.metadata as md
import inspect
import logging
from typing import Any

import pluggy

from prefect._experimental.plugins.spec import PREFECT_PLUGIN_API_VERSION

PM_PROJECT_NAME = "prefect-experimental"
EP_GROUP = "prefect.plugins"

# Create a hookimpl marker for plugins to optionally use
hookimpl = pluggy.HookimplMarker(PM_PROJECT_NAME)


def build_manager(hookspecs: type) -> pluggy.PluginManager:
    """
    Create a pluggy PluginManager and register hook specifications.

    Args:
        hookspecs: The hook specification class/protocol

    Returns:
        Configured PluginManager instance
    """
    pm = pluggy.PluginManager(PM_PROJECT_NAME)
    pm.add_hookspecs(hookspecs)
    # Allow plugins to work without @hookimpl decorator
    pm.trace.root.setwriter(lambda *args, **kwargs: None)
    return pm


def load_entry_point_plugins(
    pm: pluggy.PluginManager,
    *,
    allow: set[str] | None,
    deny: set[str] | None,
    logger: logging.Logger,
) -> None:
    """
    Discover and load plugins from entry points.

    Args:
        pm: The PluginManager to register plugins with
        allow: If set, only load plugins with names in this set
        deny: If set, skip plugins with names in this set
        logger: Logger for reporting load failures
    """
    for ep in md.entry_points(group=EP_GROUP):
        if allow and ep.name not in allow:
            logger.debug("Skipping plugin %s (not in allow list)", ep.name)
            continue
        if deny and ep.name in deny:
            logger.debug("Skipping plugin %s (in deny list)", ep.name)
            continue
        try:
            plugin = ep.load()
            # Version fence (best effort)
            requires = getattr(plugin, "PREFECT_PLUGIN_API_REQUIRES", ">=0.1,<1")
            # TODO: Optional: validate `requires` against PREFECT_PLUGIN_API_VERSION
            # using packaging.specifiers
            pm.register(plugin, name=ep.name)
            logger.debug(
                "Loaded plugin %s (requires API %s, current %s)",
                ep.name,
                requires,
                PREFECT_PLUGIN_API_VERSION,
            )
        except Exception:
            logger.exception("Failed to load plugin %s", ep.name)


async def call_async_hook(
    pm: pluggy.PluginManager, hook_name: str, **kwargs: Any
) -> list[tuple[str, Any, Exception | None]]:
    """
    Call a hook that may return coroutines.

    This function handles both sync and async hook implementations, gathering
    results and exceptions per plugin.

    Args:
        pm: The PluginManager
        hook_name: Name of the hook to call
        **kwargs: Arguments to pass to the hook

    Returns:
        List of tuples: (plugin_name, result, exception)
        - If successful: (name, result, None)
        - If failed: (name, None, exception)
    """
    hook = getattr(pm.hook, hook_name)
    results: list[tuple[str, Any, Exception | None]] = []
    for impl in hook.get_hookimpls():
        fn = impl.function
        try:
            res = fn(**kwargs)
            if inspect.iscoroutine(res):
                res = await res
            results.append((impl.plugin_name, res, None))
        except Exception as exc:
            results.append((impl.plugin_name, None, exc))
    return results
