import pytest

import prefect.core.client
from prefect.core.client import Client


@pytest.fixture
async def user_client(client):
    client = Client(http_client=client)
    prefect.core.client._clients[None] = client
    yield client
