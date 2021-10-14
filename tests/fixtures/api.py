import pytest
from httpx import AsyncClient

from prefect.orion.api.server import app


@pytest.fixture
async def client():
    """
    Yield a test client for testing the orion api
    """

    async with AsyncClient(
        app=app, base_url="https://test/api", follow_redirects=True
    ) as async_client:
        yield async_client
