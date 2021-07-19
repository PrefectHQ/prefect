import pytest

from prefect.core import flow
from prefect.core.client import Client
from prefect.orion.api import schemas


@pytest.fixture
async def user_client(client):
    client = Client(http_client=client)
    yield client


async def test_create_then_read_flow(user_client):
    @flow
    def foo():
        pass

    flow_id = await user_client.create_flow(foo)
    assert isinstance(flow_id, str)

    lookup = await user_client.read_flow(flow_id)
    assert isinstance(lookup, schemas.Flow)
    assert lookup.name == foo.name
    assert lookup.tags == list(foo.tags)
    assert lookup.parameters == foo.parameters


async def test_create_then_read_flow_run(user_client):
    @flow
    def foo():
        pass

    flow_run_id = await user_client.create_flow_run(foo)
    assert isinstance(flow_run_id, str)

    lookup = await user_client.read_flow_run(flow_run_id)
    assert isinstance(lookup, schemas.FlowRun)
    assert lookup.tags == list(foo.tags)
    assert lookup.parameters == {}
