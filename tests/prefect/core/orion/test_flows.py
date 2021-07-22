from prefect.core import flow
from prefect.core.orion.flows import create_flow, read_flow
from prefect.orion import schemas


async def test_create_then_read_flow(user_client):
    @flow
    def foo():
        pass

    flow_id = await create_flow(foo)
    assert isinstance(flow_id, str)

    lookup = await read_flow(flow_id)
    assert isinstance(lookup, schemas.api.Flow)
    assert lookup.name == foo.name
    assert lookup.tags == list(foo.tags)
    assert lookup.parameters == foo.parameters
