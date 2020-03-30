# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import logging

from prefect_server import utilities


def test_root_logger_level_responds_to_config():
    try:
        with utilities.tests.set_temporary_config("logging.level", "DEBUG"):
            utilities.logging.configure_logging().level == logging.DEBUG

        with utilities.tests.set_temporary_config("logging.level", "WARNING"):
            utilities.logging.configure_logging().level == logging.WARNING
    finally:
        # reset root_logger
        logger = utilities.logging.get_logger()
        for h in logger.handlers:
            logger.removeHandler(h)
        utilities.logging.configure_logging()


def test_get_logger_returns_root_logger():
    assert utilities.logging.get_logger() is logging.getLogger("prefect-server")


def test_get_logger_with_name_returns_child_logger():
    child_logger = logging.getLogger("prefect-server.test")
    server_logger = utilities.logging.get_logger("test")

    assert server_logger is child_logger
    assert server_logger is logging.getLogger("prefect-server").getChild("test")
