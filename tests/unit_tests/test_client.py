from uuid import UUID

import prefect
from prefect import flow
from prefect.tasks import task
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
    @flow(tags=["a", "b"])
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
        state=schemas.states.State(
            type=schemas.states.StateType.COMPLETED, message="Test!"
        ),
    )
    assert isinstance(response, schemas.responses.SetStateResponse)
    assert response.status == schemas.responses.SetStateStatus.ACCEPT

    states = client.read_flow_run_states(flow_run_id)
    assert len(states) == 1
    state = states[-1]
    assert isinstance(state, schemas.states.State)
    assert state.type == schemas.states.StateType.COMPLETED
    assert state.message == "Test!"


def test_create_then_read_task_run():
    @flow
    def foo():
        pass

    @task(tags=["a", "b"], max_retries=3)
    def bar():
        pass

    client = prefect.client.OrionClient()
    flow_run_id = client.create_flow_run(foo)
    task_run_id = client.create_task_run(bar, flow_run_id=flow_run_id)
    assert isinstance(task_run_id, UUID)

    lookup = client.read_task_run(task_run_id)
    assert isinstance(lookup, schemas.core.TaskRun)
    assert lookup.tags == list(bar.tags)
    assert lookup.task_key == bar.task_key
    assert lookup.empirical_policy == schemas.core.TaskRunPolicy(max_retries=3)


def test_set_then_read_task_run_state():
    @flow
    def foo():
        pass

    @task
    def bar():
        pass

    client = prefect.client.OrionClient()
    flow_run_id = client.create_flow_run(foo)
    task_run_id = client.create_task_run(bar, flow_run_id=flow_run_id)

    response = client.set_task_run_state(
        task_run_id,
        schemas.states.State(type=schemas.states.StateType.COMPLETED, message="Test!"),
    )

    assert isinstance(response, schemas.responses.SetStateResponse)
    assert response.status == schemas.responses.SetStateStatus.ACCEPT

    states = client.read_task_run_states(task_run_id)
    assert len(states) == 1
    state = states[-1]
    assert isinstance(state, schemas.states.State)
    assert state.type == schemas.states.StateType.COMPLETED
    assert state.message == "Test!"
