import logging
from unittest.mock import MagicMock

from prefect import utilities


def test_root_logger_level_responds_to_config():
    try:
        with utilities.configuration.set_temporary_config({"logging.level": "DEBUG"}):
            utilities.logging.configure_logging().level == logging.DEBUG

        with utilities.configuration.set_temporary_config({"logging.level": "WARNING"}):
            utilities.logging.configure_logging().level == logging.WARNING
    finally:
        # reset root_logger
        logger = utilities.logging.get_logger()
        for h in logger.handlers:
            logger.removeHandler(h)
        utilities.logging.configure_logging()


def test_remote_handler_is_configured_for_cloud(monkeypatch):
    starter = MagicMock()
    listener = MagicMock(return_value=starter)
    monkeypatch.setattr("prefect.utilities.logging.QueueListener", listener)
    try:
        with utilities.configuration.set_temporary_config(
            {"logging.log_to_cloud": True, "cloud.log": "http://foo.bar:1800/log"}
        ):
            logger = utilities.logging.configure_logging()
            assert listener.called
            remote_handler = listener.call_args[0][1]
            assert remote_handler.logger_server == "http://foo.bar:1800/log"
            assert starter.start.called
    finally:
        # reset root_logger
        logger = utilities.logging.get_logger()
        for h in logger.handlers:
            logger.removeHandler(h)
        utilities.logging.configure_logging()


def test_get_logger_returns_root_logger():
    assert utilities.logging.get_logger() is logging.getLogger("prefect")


def test_get_logger_with_name_returns_child_logger():
    child_logger = logging.getLogger("prefect.test")
    prefect_logger = utilities.logging.get_logger("test")

    assert prefect_logger is child_logger
    assert prefect_logger is logging.getLogger("prefect").getChild("test")
