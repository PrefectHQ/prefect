"""
This is a regression tests for https://github.com/PrefectHQ/prefect/issues/16115
"""

import logging
from logging.config import dictConfig

from prefect import flow

logger = logging.getLogger(__name__)
logger.setLevel("WARNING")

dictConfig({"version": 1, "incremental": False})


@flow
def myflow():
    return "Hello"


if __name__ == "__main__":
    result = myflow()

    assert result == "Hello"
