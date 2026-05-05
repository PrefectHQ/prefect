"""
Plugin startup hook orchestration.

Reads the `plugins` settings, builds a pluggy manager, runs all registered
`setup_environment` hooks (with timeout and strict-mode handling), and
returns diagnostic summaries. Public entry point is re-exported from
`prefect.plugins`.
"""

from __future__ import annotations

from typing import Any

import anyio

from prefect._internal.plugins.apply import apply_setup_result, summarize_env
from prefect._internal.plugins.diagnostics import SetupSummary
from prefect._internal.plugins.manager import (
    build_manager,
    call_async_hook,
    load_entry_point_plugins,
)
from prefect._internal.plugins.spec import HookContext, HookSpec, SetupResult
from prefect.settings import get_current_settings


async def run_startup_hooks(ctx: HookContext) -> list[SetupSummary]:
    """
    Run all registered plugin startup hooks.

    This is the main entry point for the plugin system. It:
    1. Checks if plugins are enabled via configuration
    2. Discovers and loads plugins from entry points
    3. Calls setup_environment hooks (respecting timeouts)
    4. Applies environment changes from successful hooks
    5. Returns diagnostic summaries

    Args:
        ctx: Context object with Prefect version, API URL, and logger factory

    Returns:
        List of SetupSummary objects describing what each plugin did

    Raises:
        SystemExit: In strict mode, if a required plugin fails
    """
    logger = ctx.logger_factory("prefect.plugins")
    settings = get_current_settings().plugins

    if not settings.enabled:
        logger.debug("Plugins not enabled")
        return []

    logger.debug("Initializing plugin system")
    pm = build_manager(HookSpec)
    allow = settings.allow
    deny = settings.deny
    load_entry_point_plugins(pm, allow=allow, deny=deny, logger=logger)

    summaries: list[SetupSummary] = []

    if settings.safe_mode:
        logger.info("Safe mode enabled - plugins loaded but hooks not called")
        return summaries

    # Call all hooks with timeout
    timeout = settings.setup_timeout_seconds
    results: list[tuple[str, Any, Exception | None]] = []

    try:
        with anyio.move_on_after(timeout) as cancel_scope:
            results = await call_async_hook(pm, "setup_environment", ctx=ctx)

        if cancel_scope.cancel_called:
            logger.warning("Plugin setup timed out after %.1fs", timeout)
    except Exception as e:
        logger.exception("Unexpected error during plugin setup: %s", e)

    # Process results
    for name, res, err in results:
        if err:
            logger.error("Plugin %s failed: %s", name, err)
            summaries.append(
                SetupSummary(plugin=name, env_preview={}, note=None, error=str(err))
            )
            continue

        if res is None:
            logger.debug("Plugin %s returned no changes", name)
            summaries.append(
                SetupSummary(plugin=name, env_preview={}, note=None, error=None)
            )
            continue

        try:
            apply_setup_result(res, logger)
            summaries.append(
                SetupSummary(
                    name,
                    summarize_env(dict(res.env)),
                    res.note,
                    error=None,
                )
            )
            logger.debug("Plugin %s completed successfully", name)
        except Exception as e:
            logger.exception("Failed to apply result from plugin %s", name)
            summaries.append(SetupSummary(name, {}, None, None, error=str(e)))

    # Strict failure policy
    if settings.strict:
        for name, res, err in results:
            if err:
                raise SystemExit(f"[plugins] required plugin '{name}' failed: {err}")
            if res and getattr(res, "required", False) and not res.env:
                raise SystemExit(
                    f"[plugins] required plugin '{name}' returned SetupResult with "
                    f"required=True but empty env. If no changes are needed, return "
                    f"None instead of SetupResult."
                )

    logger.debug("Plugin system initialization complete (%d plugins)", len(summaries))
    return summaries


__all__ = ["run_startup_hooks", "HookContext", "HookSpec", "SetupResult"]
