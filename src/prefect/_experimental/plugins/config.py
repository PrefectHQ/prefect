"""
Configuration and feature flags for the experimental plugin system.
"""

from __future__ import annotations

import os


def enabled() -> bool:
    """
    Check if the experimental plugin system is enabled.

    Returns:
        True if PREFECT_EXPERIMENTAL_PLUGINS is set to "1"
    """
    return os.getenv("PREFECT_EXPERIMENTAL_PLUGINS") == "1"


def timeout_seconds() -> float:
    """
    Get the timeout for plugin setup hooks.

    Returns:
        Timeout in seconds (default: 20)
    """
    return float(os.getenv("PREFECT_PLUGINS_SETUP_TIMEOUT_SECONDS", "20"))


def lists() -> tuple[set[str] | None, set[str] | None]:
    """
    Get allow and deny lists for plugins.

    Returns:
        Tuple of (allow_set, deny_set). Either may be None if not configured.
    """
    allow = os.getenv("PREFECT_PLUGINS_ALLOW")
    deny = os.getenv("PREFECT_PLUGINS_DENY")
    return (
        set(a.strip() for a in allow.split(",") if a.strip()) if allow else None,
        set(d.strip() for d in deny.split(",") if d.strip()) if deny else None,
    )


def strict() -> bool:
    """
    Check if strict mode is enabled.

    In strict mode, any plugin error marked required=True will abort Prefect startup.

    Returns:
        True if PREFECT_PLUGINS_STRICT is set to "1"
    """
    return os.getenv("PREFECT_PLUGINS_STRICT") == "1"


def safe_mode() -> bool:
    """
    Check if safe mode is enabled.

    In safe mode, plugins are loaded but hooks are not called. Useful for debugging.

    Returns:
        True if PREFECT_PLUGINS_SAFE_MODE is set to "1"
    """
    return os.getenv("PREFECT_PLUGINS_SAFE_MODE") == "1"
