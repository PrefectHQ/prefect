import pytest

import prefect.core.client
from prefect.core.client import Client


@pytest.fixture
async def user_client(client):
    with Client(http_client=client) as client:
        yield client
