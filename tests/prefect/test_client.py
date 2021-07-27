from uuid import UUID

import prefect
from prefect import flow
from prefect.orion import schemas


def test_create_then_read_flow():
    @flow
    def foo():
        pass

    client = prefect.client.OrionClient()
    flow_id = client.create_flow(foo)
    assert isinstance(flow_id, UUID)

    lookup = client.read_flow(flow_id)
    assert isinstance(lookup, schemas.core.Flow)
    assert lookup.name == foo.name
    assert lookup.tags == list(foo.tags)
    assert lookup.parameters == foo.parameters


def test_create_then_read_flow_run():
    @flow
    def foo():
        pass

    client = prefect.client.OrionClient()
    flow_run_id = client.create_flow_run(foo)
    assert isinstance(flow_run_id, UUID)

    lookup = client.read_flow_run(flow_run_id)
    assert isinstance(lookup, schemas.core.FlowRun)
    assert lookup.tags == list(foo.tags)

    # TODO: Check parameters
