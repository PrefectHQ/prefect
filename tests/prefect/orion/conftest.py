import pytest
import inspect
from httpx import AsyncClient

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from prefect.orion.api.server import app
from prefect.orion.api.dependencies import get_session
from prefect.orion.utilities.database import reset_db
from prefect.orion.utilities.settings import Settings

from .fixtures.database_fixtures import *


def pytest_collection_modifyitems(session, config, items):
    """
    Modify tests prior to execution
    """
    for item in items:
        # automatically add @pytest.mark.asyncio to async tests
        if isinstance(item, pytest.Function) and inspect.iscoroutinefunction(
            item.function
        ):
            item.add_marker(pytest.mark.asyncio)


@pytest.fixture
async def client(database_session):
    """
    Yield a test client for testing the api
    """

    # override the default get session logic to use
    # test database instead of actual db
    def _get_session_override():
        return database_session

    app.dependency_overrides[get_session] = _get_session_override

    async with AsyncClient(app=app, base_url="http://test") as async_client:
        yield async_client
