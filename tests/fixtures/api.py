import httpx
import pytest
from httpx import ASGITransport

from prefect.orion.api.server import create_app


@pytest.fixture()
def app():
    return create_app(ephemeral=True)


@pytest.fixture
async def client(app):
    """
    Yield a test client for testing the orion api
    """

    async with httpx.AsyncClient(app=app, base_url="https://test/api") as async_client:
        yield async_client


@pytest.fixture
async def client_without_exceptions(app):
    """
    Yield a test client that does not raise app exceptions.

    This is useful if you need to test e.g. 500 error responses.
    """
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with httpx.AsyncClient(
        transport=transport, base_url="https://test/api"
    ) as async_client:
        yield async_client
