import logging
from logging.config import dictConfig

from prefect import flow

"\nThis is a regression tests for https://github.com/PrefectHQ/prefect/issues/16115\n"
logger = logging.getLogger(__name__)
logger.setLevel("WARNING")
dictConfig({"version": 1, "incremental": False})


@flow
def myflow():
    return "Hello"


def test_setup_logging():
    """Test for setup_logging."""
    result = myflow()
    assert result == "Hello"
