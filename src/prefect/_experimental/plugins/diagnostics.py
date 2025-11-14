"""
Diagnostic data structures for plugin system.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SetupSummary:
    """
    Summary of a plugin's setup_environment execution.

    Attributes:
        plugin: Name of the plugin
        env_preview: Preview of environment variables set (with redacted values)
        note: Human-readable note from the plugin, if any
        error: Error message if the plugin failed, or None if successful
    """

    plugin: str
    env_preview: dict[str, str]
    note: str | None
    error: str | None
