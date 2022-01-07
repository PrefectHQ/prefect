import asyncio
import inspect
import logging
import pathlib

import pytest

from .fixtures.api import *
from .fixtures.client import *
from .fixtures.database import *
from .fixtures.logging import *


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "service(arg) a service integration test. For example, 'docker'."
    )


def pytest_addoption(parser):
    parser.addoption(
        "--service",
        action="append",
        metavar="SERVICE",
        default=[],
        help="include service integration tests for SERVICE.",
    )
    parser.addoption(
        "--all-services",
        action="store_true",
        default=False,
        help="include all service integration tests",
    )


def pytest_collection_modifyitems(session, config, items):
    """
    Modify all tests to automatically and transparently support asyncio
    """
    for item in items:
        # automatically add @pytest.mark.asyncio to async tests
        if isinstance(item, pytest.Function) and inspect.iscoroutinefunction(
            item.function
        ):
            item.add_marker(pytest.mark.asyncio)

    if config.getoption("--all-services"):
        # Do not skip any service tests
        return

    run_services = set(config.getoption("--service"))
    for item in items:
        item_services = {mark.args[0] for mark in item.iter_markers(name="service")}
        missing_services = item_services.difference(run_services)
        if missing_services:
            item.add_marker(
                pytest.mark.skip(
                    f"Requires service {', '.join(repr(s) for s in missing_services)}. "
                    "Use '--service NAME' to include."
                )
            )


@pytest.fixture(scope="session")
def event_loop(request):
    """
    Redefine the event loop to support session/module-scoped fixtures;
    see https://github.com/pytest-dev/pytest-asyncio/issues/68
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()

    # configure asyncio logging to capture long running tasks
    asyncio_logger = logging.getLogger("asyncio")
    asyncio_logger.setLevel("WARNING")
    asyncio_logger.addHandler(logging.StreamHandler())
    loop.set_debug(True)
    loop.slow_callback_duration = 0.1

    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture
def tests_dir() -> pathlib.Path:
    return pathlib.Path(__file__).parent
