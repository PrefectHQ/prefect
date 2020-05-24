# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import logging

from prefect_server.configuration import config


def configure_logging() -> logging.Logger:
    """
    Creates a "prefect-server" root logger with a `StreamHandler` that has level and formatting
    set from `prefect-server.config`.

    Returns:
        logging.Logger
    """
    logger = logging.getLogger("prefect-server")
    handler = logging.StreamHandler()
    formatter = logging.Formatter(config.logging.format)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(config.logging.level)
    return logger


prefect_logger = configure_logging()


def get_logger(name: str = None) -> logging.Logger:
    """
    Returns a "prefect-server" logger.

    Args:
        - name (str): if `None`, the root Prefect logger is returned. If provided, a child
            logger of the name `"prefect-server.{name}"` is returned. The child logger inherits
            the root logger's settings.

    Returns:
        logging.Logger
    """
    if name is None:
        return prefect_logger
    else:
        return prefect_logger.getChild(name)
