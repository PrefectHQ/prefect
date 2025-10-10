"""
Safe application of plugin setup results with secret redaction.
"""

from __future__ import annotations

import logging
import os

from prefect._experimental.plugins.spec import SetupResult

REDACT_KEYS = ("SECRET", "TOKEN", "PASSWORD", "KEY")


def redact(key: str, value: str) -> str:
    """
    Redact sensitive values based on key name heuristics.

    Args:
        key: Environment variable name
        value: Environment variable value

    Returns:
        Redacted value if the key appears sensitive, otherwise truncated value
    """
    k = key.upper()
    if any(tag in k for tag in REDACT_KEYS):
        return "••••••"
    return value if len(value) <= 64 else value[:20] + "…"


def apply_setup_result(result: SetupResult, logger: logging.Logger) -> None:
    """
    Apply environment changes to the current process.

    This function never logs secrets - all values are redacted based on key name
    heuristics.

    Args:
        result: The SetupResult containing environment variables to set
        logger: Logger to use for informational messages
    """
    for k, v in (result.env or {}).items():
        os.environ[str(k)] = str(v)
    note = result.note or ""
    logger.info(
        "plugin env applied%s",
        f" — {note}" if note else "",
    )


def summarize_env(env: dict[str, str]) -> dict[str, str]:
    """
    Create a safe summary of environment variables with redacted values.

    Args:
        env: Dictionary of environment variables

    Returns:
        Dictionary with same keys but redacted values
    """
    return {k: redact(k, v) for k, v in env.items()}
