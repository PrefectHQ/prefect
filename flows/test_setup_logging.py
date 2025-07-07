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


def test_setup_logging():
    result = myflow()
    assert result == "Hello"
