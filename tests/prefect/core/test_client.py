from prefect.core.client import Client
from prefect.core import flow
from prefect.orion.api import schemas


async def test_create_then_read_flow():
    @flow
    def foo():
        pass

    client = Client()

    flow_id = await client.create_flow(foo)
    assert isinstance(flow_id, str)

    lookup = await client.read_flow(flow_id)
    assert isinstance(lookup, schemas.Flow)
    assert lookup.name == foo.name
    assert lookup.tags == foo.tags
    assert lookup.parameters == foo.parameters
