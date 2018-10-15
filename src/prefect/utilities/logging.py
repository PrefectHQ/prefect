# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula
import logging

from prefect.configuration import config


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("prefect")
    handler = logging.StreamHandler()
    formatter = logging.Formatter(config.logging.format)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(config.logging.level)
    return logger


prefect_logger = configure_logging()


def get_logger(name: str = None) -> logging.Logger:
    if name is None:
        return prefect_logger
    else:
        return prefect_logger.getChild(name)
