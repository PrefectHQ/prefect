import asyncio
import inspect
import logging

import pytest
from httpx import AsyncClient

from prefect.orion.api.server import app
from prefect.orion.utilities.database import Base, get_engine


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
async def client():
    """
    Yield a test client for testing the api
    """

    async with AsyncClient(app=app, base_url="https://test") as async_client:
        yield async_client


@pytest.fixture(scope="session")
async def database_engine():
    engine = get_engine()

    try:
        # populate database tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine

    finally:
        # drop database tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        # dispose of engine
        await engine.dispose()
