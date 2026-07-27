"""Fixtures shared by the whole `prefect-sandbox` test suite."""

from __future__ import annotations

import logging
from collections.abc import Generator

import pytest

from prefect.testing.utilities import prefect_test_harness


@pytest.fixture(scope="session", autouse=True)
def prefect_db() -> Generator[None, None, None]:
    """Point the whole session at a temporary Prefect database.

    This is what makes `Block.save()` / `Block.load()` work in tests. Session
    scoped and autouse because the harness is not cheap — it stands up a temp
    SQLite database *and* a real subprocess API server, and under
    `pytest-xdist` every worker already pays for its own.
    """
    with prefect_test_harness():
        yield


@pytest.fixture
def prefect_caplog(
    caplog: pytest.LogCaptureFixture,
) -> Generator[pytest.LogCaptureFixture, None, None]:
    """`caplog`, but with records from the `prefect` logger tree reaching it.

    Prefect switches propagation off on its loggers, so `caplog` captures
    nothing from them by default. Core ships an autouse fixture that does this,
    but it lives in `prefect.testing.fixtures`, and importing that module drags
    in an autouse `use_hosted_api_server` that would start a uvicorn subprocess
    for every test in this package.
    """
    logger = logging.getLogger("prefect")
    logger.propagate = True
    try:
        yield caplog
    finally:
        logger.propagate = False


@pytest.fixture
def prefect_task_runs_caplog(
    prefect_caplog: pytest.LogCaptureFixture,
) -> Generator[pytest.LogCaptureFixture, None, None]:
    """`prefect_caplog`, extended to the run loggers.

    Inside a flow or task run a Block's `.logger` is the *run* logger
    (`prefect.task_runs`), not `prefect.<ClassName>` — so assertions about
    output streamed from a sandbox need this fixture rather than
    `prefect_caplog` whenever the operation executes inside a run.
    """
    logger = logging.getLogger("prefect.task_runs")
    logger.propagate = True
    try:
        yield prefect_caplog
    finally:
        logger.propagate = False
