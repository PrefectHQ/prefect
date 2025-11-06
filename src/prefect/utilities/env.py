"""Utilities for parsing environment variables."""

import os
from typing import Optional

from pydantic import TypeAdapter, ValidationError

_BOOL_ADAPTER: TypeAdapter[bool] = TypeAdapter(bool)


def parse_bool_env(var_name: str, default: bool = False) -> bool:
    """
    Parse a boolean environment variable using Pydantic's boolean coercion rules.

    Uses Pydantic's TypeAdapter to parse boolean values, which accepts common
    truthy and falsy values case-insensitively:
    - Truthy: "1", "true", "t", "yes", "y", "on"
    - Falsy: "0", "false", "f", "no", "n", "off"
    - If the variable is not set, returns the default value
    - If the variable is set to an invalid value, returns the default value

    Args:
        var_name: The name of the environment variable to parse
        default: The default value to return if the variable is not set or invalid

    Returns:
        The parsed boolean value

    Examples:
        >>> os.environ["MY_FLAG"] = "1"
        >>> parse_bool_env("MY_FLAG")
        True
        >>> os.environ["MY_FLAG"] = "false"
        >>> parse_bool_env("MY_FLAG")
        False
        >>> parse_bool_env("NONEXISTENT_FLAG", default=True)
        True
        >>> os.environ["MY_FLAG"] = "invalid"
        >>> parse_bool_env("MY_FLAG")
        False
    """
    value: Optional[str] = os.getenv(var_name)
    if value is None:
        return default
    try:
        return _BOOL_ADAPTER.validate_python(value)
    except ValidationError:
        return default
