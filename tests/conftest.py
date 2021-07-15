import pytest
import inspect
from httpx import AsyncClient

from prefect.orion.api.server import app
from prefect.orion.utilities.server import get_session

from .fixtures.database_fixtures import database_engine, database_session

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

        # if the item is in a deprecated subdirectory, mark it as deprecated
        if "deprecated/" in str(item.fspath):
            item.add_marker(pytest.mark.deprecated)


@pytest.fixture(autouse=True)
async def test_client(database_session):
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