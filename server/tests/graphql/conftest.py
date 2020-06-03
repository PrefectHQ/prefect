# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import httpx
import pytest
from box import Box

import prefect
from prefect.engine.state import Running
from prefect_server import api, config
from prefect_server.database import models
from prefect_server.services.graphql import app

GRAPHQL_URL = config.services.graphql.path


@pytest.fixture
async def client():
    yield httpx.AsyncClient(app=app, base_url="http://prefect.io")


@pytest.fixture
async def run_query(client):
    async def run_query(query, variables=None, headers=None):
        headers = headers or {}
        response = await client.post(
            GRAPHQL_URL,
            json=dict(query=query, variables=variables or {}),
            headers=headers,
        )
        result = Box(response.json())
        return result

    return run_query
