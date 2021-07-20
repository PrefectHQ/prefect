from prefect.core import flow
from prefect.orion.api import schemas
from prefect.core.client import read_flow, create_flow, read_flow_run, create_flow_run


async def test_create_then_read_flow(user_client):
    @flow
    def foo():
        pass

    flow_id = await create_flow(foo)
    assert isinstance(flow_id, str)

    lookup = await read_flow(flow_id)
    assert isinstance(lookup, schemas.Flow)
    assert lookup.name == foo.name
    assert lookup.tags == list(foo.tags)
    assert lookup.parameters == foo.parameters


async def test_create_then_read_flow_run(user_client):
    @flow
    def foo():
        pass

    flow_run_id = await create_flow_run(foo)
    assert isinstance(flow_run_id, str)

    lookup = await read_flow_run(flow_run_id)
    assert isinstance(lookup, schemas.FlowRun)
    assert lookup.tags == list(foo.tags)
    assert lookup.parameters == {}
