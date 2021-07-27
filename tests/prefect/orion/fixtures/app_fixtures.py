from contextlib import contextmanager

import pytest
from httpx import AsyncClient

from prefect.client import OrionClient
from prefect.orion.api.dependencies import get_session
from prefect.orion.api.server import app


@pytest.fixture(autouse=True)
async def override_app_database_session(database_session):
    """
    Overrides the Orion server's database session to always
    use the test fixture session.
    """

    # override the default get session logic to use
    # test database
    def _get_session_override():
        return database_session

    app.dependency_overrides[get_session] = _get_session_override


@pytest.fixture
async def client(override_app_database_session):
    """
    Yield a test client for testing the api
    """

    async with AsyncClient(app=app, base_url="https://test") as async_client:
        yield async_client


@pytest.fixture
async def orion_client(client, monkeypatch):
    @contextmanager
    def yield_client(_):
        yield client

    # Patch the ASGIClient to use the existing test client
    monkeypatch.setattr("prefect.client._ASGIClient._httpx_client", yield_client)

    yield OrionClient()
