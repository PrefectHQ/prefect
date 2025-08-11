"""
Shared validation utilities for Prefect settings.

This module provides validation functions that can be used across different
parts of the settings system without creating circular dependencies.
"""

from __future__ import annotations

import re
from typing import FrozenSet, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from prefect.settings.legacy import Setting

# Precompiled regex for better performance - allows only alphanumeric and underscores
_LOGGING_PATH_PATTERN = re.compile(r"^[A-Z0-9_]+$")


def is_valid_logging_setting(setting_name: str) -> bool:
    """
    Validate that a setting name follows the documented PREFECT_LOGGING_* pattern.

    As documented, any value in Prefect's logging configuration can be overridden
    through a Prefect setting of the form PREFECT_LOGGING_[PATH]_[TO]_[KEY]=value.

    This function validates that the setting follows this pattern and contains only
    safe characters to prevent injection attacks.

    Args:
        setting_name: The setting name to validate

    Returns:
        True if the setting is a valid PREFECT_LOGGING_* setting, False otherwise
    """
    if not isinstance(setting_name, str) or not setting_name.startswith(
        "PREFECT_LOGGING_"
    ):
        return False

    # Extract the path portion after PREFECT_LOGGING_
    path_portion = setting_name[16:]  # len("PREFECT_LOGGING_") = 16

    # Validate: non-empty, only uppercase letters, digits, and underscores
    return bool(path_portion) and _LOGGING_PATH_PATTERN.match(path_portion) is not None


def is_setting_or_valid_logging(
    setting_name: str, valid_setting_names: FrozenSet[str]
) -> bool:
    """
    Check if a setting name is either a valid Prefect setting or a valid logging override.

    Args:
        setting_name: The setting name to validate
        valid_setting_names: Set of all valid Prefect setting names

    Returns:
        True if the setting is valid, False otherwise
    """
    return setting_name in valid_setting_names or is_valid_logging_setting(setting_name)


def should_allow_string_key(setting_key: Union[str, Setting]) -> bool:
    """
    Determine if a setting key should be kept as a string rather than converted to Setting.

    Args:
        setting_key: The setting key to check

    Returns:
        True if the key should remain as a string, False otherwise
    """
    return isinstance(setting_key, str) and is_valid_logging_setting(setting_key)
