import logging
from unittest.mock import MagicMock

from prefect import utilities


def test_root_logger_level_responds_to_config():
    try:
        with utilities.configuration.set_temporary_config({"logging.level": "DEBUG"}):
            assert (
                utilities.logging.configure_logging(testing=True).level == logging.DEBUG
            )

        with utilities.configuration.set_temporary_config({"logging.level": "WARNING"}):
            assert (
                utilities.logging.configure_logging(testing=True).level
                == logging.WARNING
            )
    finally:
        # reset root_logger
        logger = utilities.logging.configure_logging(testing=True)
        logger.handlers = []


def test_remote_handler_is_configured_for_cloud():
    try:
        with utilities.configuration.set_temporary_config(
            {"logging.log_to_cloud": True}
        ):
            logger = utilities.logging.configure_logging(testing=True)
            assert hasattr(logger.handlers[-1], "client")
    finally:
        # reset root_logger
        logger = utilities.logging.configure_logging(testing=True)
        logger.handlers = []


def test_remote_handler_captures_errors_and_logs_them(caplog):
    try:
        with utilities.configuration.set_temporary_config(
            {"logging.log_to_cloud": True}
        ):
            logger = utilities.logging.configure_logging(testing=True)
            assert hasattr(logger.handlers[-1], "client")
            child_logger = logger.getChild("sub-test")
            child_logger.critical("this should raise an error in the handler")

            critical_logs = [r for r in caplog.records if r.levelname == "CRITICAL"]
            assert len(critical_logs) == 2

            assert (
                "Failed to write log with error"
                in [
                    log.message for log in critical_logs if log.name == "CloudHandler"
                ].pop()
            )
    finally:
        # reset root_logger
        logger = utilities.logging.configure_logging(testing=True)
        logger.handlers = []


def test_get_logger_returns_root_logger():
    assert utilities.logging.get_logger() is logging.getLogger("prefect")


def test_get_logger_with_name_returns_child_logger():
    child_logger = logging.getLogger("prefect.test")
    prefect_logger = utilities.logging.get_logger("test")

    assert prefect_logger is child_logger
    assert prefect_logger is logging.getLogger("prefect").getChild("test")
