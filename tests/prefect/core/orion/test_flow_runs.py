from prefect.core import flow
from prefect.core.orion.flow_runs import create_flow_run, read_flow_run
from prefect.orion import schemas


async def test_create_then_read_flow_run(user_client):
    @flow
    def foo():
        pass

    flow_run_id = await create_flow_run(foo)
    assert isinstance(flow_run_id, str)

    lookup = await read_flow_run(flow_run_id)
    assert isinstance(lookup, schemas.api.FlowRun)
    assert lookup.tags == list(foo.tags)

    # TODO: Check parameters
