"""
Configuration and feature flags for the experimental plugin system.
"""

from __future__ import annotations

from prefect.settings.models.root import Settings


def _get_settings():
    """
    Get settings, creating a fresh instance to pick up environment changes.

    This uses Settings() directly rather than get_current_settings() to ensure
    we always read from the current environment, which is important for testing
    with settings context managers like temporary_settings.
    """
    from prefect.context import SettingsContext

    # If we're in a settings context, use those settings
    # Otherwise create a fresh Settings object from environment
    settings_context = SettingsContext.get()
    if settings_context is not None:
        return settings_context.settings

    return Settings()


def enabled() -> bool:
    """
    Check if the experimental plugin system is enabled.

    Returns:
        True if experiments.plugins.enabled is True
    """
    return _get_settings().experiments.plugins.enabled


def timeout_seconds() -> float:
    """
    Get the timeout for plugin setup hooks.

    Returns:
        Timeout in seconds (default: 20)
    """
    return _get_settings().experiments.plugins.setup_timeout_seconds


def lists() -> tuple[set[str] | None, set[str] | None]:
    """
    Get allow and deny lists for plugins.

    Returns:
        Tuple of (allow_set, deny_set). Either may be None if not configured.
    """
    settings = _get_settings().experiments.plugins
    allow = settings.allow
    deny = settings.deny
    return (
        set(a.strip() for a in allow.split(",") if a.strip()) if allow else None,
        set(d.strip() for d in deny.split(",") if d.strip()) if deny else None,
    )


def strict() -> bool:
    """
    Check if strict mode is enabled.

    In strict mode, any plugin error marked required=True will abort Prefect startup.

    Returns:
        True if experiments.plugins.strict is True
    """
    return _get_settings().experiments.plugins.strict


def safe_mode() -> bool:
    """
    Check if safe mode is enabled.

    In safe mode, plugins are loaded but hooks are not called. Useful for debugging.

    Returns:
        True if experiments.plugins.safe_mode is True
    """
    return _get_settings().experiments.plugins.safe_mode
