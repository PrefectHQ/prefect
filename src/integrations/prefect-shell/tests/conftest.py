import logging

import pytest


@pytest.fixture(scope="function")
def prefect_caplog(caplog):
    logger = logging.getLogger("prefect")

    # TODO: Determine a better pattern for this and expose for all tests
    logger.propagate = True

    try:
        yield caplog
    finally:
        logger.propagate = False


@pytest.fixture(scope="function")
def prefect_task_runs_caplog(prefect_caplog):
    logger = logging.getLogger("prefect.task_runs")

    # TODO: Determine a better pattern for this and expose for all tests
    logger.propagate = True

    try:
        yield prefect_caplog
    finally:
        logger.propagate = False
