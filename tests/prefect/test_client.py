from uuid import UUID


from prefect import flow
from prefect.orion import schemas


def test_create_then_read_flow(orion_client):
    @flow
    def foo():
        pass

    flow_id = orion_client.create_flow(foo)
    assert isinstance(flow_id, UUID)

    lookup = orion_client.read_flow(flow_id)
    assert isinstance(lookup, schemas.core.Flow)
    assert lookup.name == foo.name
    assert lookup.tags == list(foo.tags)
    assert lookup.parameters == foo.parameters


def test_create_then_read_flow_run(orion_client):
    @flow
    def foo():
        pass

    flow_run_id = orion_client.create_flow_run(foo)
    assert isinstance(flow_run_id, UUID)

    lookup = orion_client.read_flow_run(flow_run_id)
    assert isinstance(lookup, schemas.core.FlowRun)
    assert lookup.tags == list(foo.tags)


def test_create_then_read_flow_run_state(orion_client):
    @flow
    def foo():
        pass

    flow_run_id = orion_client.create_flow_run(foo)
    state = orion_client.create_flow_run_state(
        flow_run_id, state=schemas.core.StateType.COMPLETED, message="Test!"
    )
    assert isinstance(state, schemas.core.State)

    lookup = orion_client.read_flow_run_state(state.id)
    assert isinstance(lookup, schemas.core.State)
    assert lookup.type == schemas.core.StateType.COMPLETED
    assert lookup.message == "Test!"
