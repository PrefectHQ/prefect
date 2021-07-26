import inspect
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from prefect.client import OrionClient
from prefect.orion.api.dependencies import get_session
from prefect.orion.api.server import app
from prefect.orion.utilities.database import reset_db
from prefect.orion.utilities.settings import Settings

from .orion.fixtures.database_fixtures import *


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


@pytest.fixture
def orion_client(client, monkeypatch):
    with OrionClient(http_client=client) as user_client:
        monkeypatch.setattr(
            "prefect.client.OrionClient", MagicMock(return_value=user_client)
        )
        yield user_client
