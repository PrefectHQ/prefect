import pytest
from prefect.client import OrionClient


@pytest.fixture
async def orion_client():
    async with OrionClient() as client:
        yield client
