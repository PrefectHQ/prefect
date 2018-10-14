# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import logging

from prefect import config

root_logger = logging.getLogger()


def configure_logging(root_logger_name: str = "prefect") -> None:
    global root_logger
    root_logger = logging.getLogger(root_logger_name)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(config.logging.format)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, config.logging.level))


def get_logger(name: str = None) -> logging.Logger:
    if name is None:
        return root_logger
    else:
        return root_logger.getChild(name)


configure_logging()
