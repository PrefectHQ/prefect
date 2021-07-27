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


def test_set_then_read_flow_run_state():
    @flow
    def foo():
        pass

    client = prefect.client.OrionClient()
    flow_run_id = client.create_flow_run(foo)
    response = client.set_flow_run_state(
        flow_run_id,
        state=schemas.core.State(
            type=schemas.core.StateType.COMPLETED, message="Test!"
        ),
    )
    assert isinstance(response, schemas.responses.SetStateResponse)
    assert response.status == schemas.responses.SetStateStatus.ACCEPT
    assert response.new_state is None

    states = client.read_flow_run_states(flow_run_id)
    assert len(states) == 1
    state = states[-1]
    assert isinstance(state, schemas.core.State)
    assert state.type == schemas.core.StateType.COMPLETED
    assert state.message == "Test!"
