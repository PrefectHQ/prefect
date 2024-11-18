import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from opentelemetry.sdk._logs import LoggingHandler

_log_handler: Optional["LoggingHandler"] = None


def set_log_handler(log_handler: Optional["LoggingHandler"]) -> None:
    """Set the OTLP log handler."""
    global _log_handler
    _log_handler = log_handler


def get_log_handler() -> Optional["LoggingHandler"]:
    """Get the OTLP log handler."""
    global _log_handler
    return _log_handler


def add_telemetry_log_handler(logger: logging.Logger) -> None:
    """Add the OTLP log handler to the given logger if the log handler has
    been configured."""
    if log_handler := get_log_handler():
        logger.addHandler(log_handler)
