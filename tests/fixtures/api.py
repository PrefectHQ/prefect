import pytest
from httpx import AsyncClient, Response

from prefect.orion.api.server import app


class _OrionTestAsyncClient(AsyncClient):
    """Spite class. httpx.AsyncClient.get does not accept `json` as an arg"""

    async def get(self, *args, **kwargs) -> Response:
        """
        Send a `GET` request.

        **Parameters**: See `httpx.request`.
        """
        return await self.request("GET", *args, **kwargs)


@pytest.fixture()
async def OrionTestAsyncClient():
    return _OrionTestAsyncClient


@pytest.fixture
async def client(OrionTestAsyncClient):
    """
    Yield a test client for testing the orion api
    """

    async with OrionTestAsyncClient(app=app, base_url="https://test") as async_client:
        yield async_client
