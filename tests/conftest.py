import asyncio
import inspect
import logging
import pathlib

import pytest

from .fixtures.api import *
from .fixtures.client import *
from .fixtures.database import *


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
