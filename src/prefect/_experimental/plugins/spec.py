"""
Experimental plugin API specification.

This module defines the hook specification and data structures for Prefect's
experimental plugin system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Mapping, Optional

import pluggy

# Bump this when breaking the hook contract
PREFECT_PLUGIN_API_VERSION = "0.1"

hookspec = pluggy.HookspecMarker("prefect-experimental")


@dataclass
class HookContext:
    """
    Context provided to plugin hooks at startup.

    Attributes:
        prefect_version: The version of Prefect running
        api_url: The configured Prefect API URL, if any
        logger_factory: Factory function to create a stdlib logger for the plugin
    """

    prefect_version: str
    api_url: str | None
    # Logger factory returns a stdlib logger; plugins should use this.
    logger_factory: Callable[[str], logging.Logger]
    # Future: async Prefect client getter, settings snapshot, etc.


@dataclass
class SetupResult:
    """
    Result returned by a plugin's setup_environment hook.

    Attributes:
        env: Environment variables to set (e.g., AWS_* variables)
        note: Short, non-secret human-readable hint about what was configured
        required: If True and hook fails, abort in strict mode
    """

    env: Mapping[str, str]  # e.g. AWS_* variables
    note: Optional[str] = None  # short, non-secret human hint
    required: bool = False  # if True and hook fails -> abort (in strict mode)


class HookSpec:
    """
    Plugin hook specification.

    Plugins should implement the methods defined here to provide startup hooks.
    """

    @hookspec
    def setup_environment(self, *, ctx: HookContext) -> Optional[SetupResult]:
        """
        Prepare process environment for Prefect and its children.

        This hook is called before Prefect CLI commands, workers, or agents
        start their main work. It allows plugins to configure environment
        variables, authenticate with external services, or perform other
        setup tasks.

        Args:
            ctx: Context object with Prefect version, API URL, and logger factory

        Returns:
            SetupResult with environment variables to set, or None to indicate
            no changes are needed.

        Important:
            - Must not print secrets or write sensitive data to disk by default
            - Should be idempotent
            - May be async or sync
            - Exceptions are caught and logged unless required=True in strict mode
        """
