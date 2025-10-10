"""
Bootstrap utilities for CLI initialization, including plugin system integration.
"""

from __future__ import annotations

import logging

import anyio

from prefect import __version__
from prefect._experimental.plugins import run_startup_hooks
from prefect._experimental.plugins.spec import HookContext
from prefect.logging import get_logger
from prefect.settings import PREFECT_API_URL


def _logger_factory(name: str) -> logging.Logger:
    """
    Create a logger for plugins.

    Args:
        name: Logger name

    Returns:
        Configured stdlib logger
    """
    return get_logger(name)


def _make_ctx() -> HookContext:
    """
    Create a HookContext for plugin startup.

    Returns:
        HookContext with current Prefect configuration
    """
    return HookContext(
        prefect_version=__version__,
        api_url=str(PREFECT_API_URL.value()) if PREFECT_API_URL.value() else None,
        logger_factory=_logger_factory,
    )


def run_with_plugins() -> None:
    """
    Run plugin startup hooks synchronously.

    This function should be called early in the CLI startup process,
    before any commands execute. It will:
    - Check if plugins are enabled
    - Load and execute plugin startup hooks
    - Apply environment changes from successful plugins

    The function runs async plugin hooks using anyio.run() and handles
    all errors internally, never raising exceptions to the CLI layer.
    """

    async def _setup() -> None:
        await run_startup_hooks(_make_ctx())

    try:
        anyio.run(_setup)
    except SystemExit:
        # Re-raise SystemExit from strict mode plugin failures
        raise
    except Exception as e:
        # Log but don't crash on unexpected errors
        logger = get_logger("prefect.plugins")
        logger.exception("Unexpected error during plugin initialization: %s", e)
