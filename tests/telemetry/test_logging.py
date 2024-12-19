import logging

from prefect.telemetry.bootstrap import setup_telemetry
from prefect.telemetry.logging import (
    add_telemetry_log_handler,
    get_log_handler,
    set_log_handler,
)


def test_add_telemetry_log_handler_with_handler():
    logger = logging.getLogger("test")
    initial_handlers = list(logger.handlers)

    setup_telemetry()

    handler = get_log_handler()
    assert handler is not None

    add_telemetry_log_handler(logger)
    assert list(logger.handlers) == initial_handlers + [handler]


def test_add_telemetry_log_handler_without_handler():
    logger = logging.getLogger("test")
    initial_handlers = list(logger.handlers)

    set_log_handler(None)

    add_telemetry_log_handler(logger)
    assert list(logger.handlers) == initial_handlers
