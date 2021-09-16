from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

import pytest
from pydantic import BaseModel

from prefect import flow
from prefect.client import OrionClient
from prefect.orion import schemas
from prefect.orion.orchestration.rules import OrchestrationResult
from prefect.orion.schemas.data import DataDocument
from prefect.tasks import task
from prefect.orion.schemas.schedules import IntervalSchedule


async def test_create_then_read_flow(orion_client):
    @flow
    def foo():
        pass

    flow_id = await orion_client.create_flow(foo)
    assert isinstance(flow_id, UUID)

    lookup = await orion_client.read_flow(flow_id)
    assert isinstance(lookup, schemas.core.Flow)
    assert lookup.name == foo.name
    assert lookup.tags == list(foo.tags)


async def test_create_then_read_deployment(orion_client):
    @flow
    def foo():
        pass

    flow_id = await orion_client.create_flow(foo)
    schedule = IntervalSchedule(interval=timedelta(days=1))
    flow_data = DataDocument.encode("cloudpickle", foo)

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="test-deployment",
        flow_data=flow_data,
        schedule=schedule,
    )

    lookup = await orion_client.read_deployment(deployment_id)
    assert isinstance(lookup, schemas.core.Deployment)
    assert lookup.name == "test-deployment"
    assert lookup.flow_data == flow_data
    assert lookup.schedule == schedule


async def test_read_deployment_by_name(orion_client):
    @flow
    def foo():
        pass

    flow_id = await orion_client.create_flow(foo)
    schedule = IntervalSchedule(interval=timedelta(days=1))
    flow_data = DataDocument.encode("cloudpickle", foo)

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="test-deployment",
        flow_data=flow_data,
        schedule=schedule,
    )

    lookup = await orion_client.read_deployment_by_name("foo/test-deployment")
    assert isinstance(lookup, schemas.core.Deployment)
    assert lookup.id == deployment_id
    assert lookup.name == "test-deployment"
    assert lookup.flow_data == flow_data
    assert lookup.schedule == schedule


async def test_create_then_read_flow_run(orion_client):
    @flow(tags=["a", "b"])
    def foo():
        pass

    flow_run_id = await orion_client.create_flow_run(foo)
    assert isinstance(flow_run_id, UUID)

    lookup = await orion_client.read_flow_run(flow_run_id)
    assert isinstance(lookup, schemas.core.FlowRun)
    assert lookup.tags == list(foo.tags)
    assert lookup.state is None


async def test_create_then_read_flow_run_with_state(orion_client):
    @flow(tags=["a", "b"])
    def foo():
        pass

    flow_run_id = await orion_client.create_flow_run(
        foo, state=schemas.states.Running()
    )
    lookup = await orion_client.read_flow_run(flow_run_id)
    assert lookup.state.is_running()


async def test_set_then_read_flow_run_state(orion_client):
    @flow
    def foo():
        pass

    flow_run_id = await orion_client.create_flow_run(foo)
    response = await orion_client.set_flow_run_state(
        flow_run_id,
        state=schemas.states.Completed(message="Test!"),
    )
    assert isinstance(response, OrchestrationResult)
    assert response.status == schemas.responses.SetStateStatus.ACCEPT

    states = await orion_client.read_flow_run_states(flow_run_id)
    assert len(states) == 1
    state = states[-1]
    assert isinstance(state, schemas.states.State)
    assert state.type == schemas.states.StateType.COMPLETED
    assert state.message == "Test!"


async def test_create_then_read_task_run(orion_client):
    @flow
    def foo():
        pass

    @task(tags=["a", "b"], retries=3)
    def bar(orion_client):
        pass

    flow_run_id = await orion_client.create_flow_run(foo)
    task_run_id = await orion_client.create_task_run(bar, flow_run_id=flow_run_id)
    assert isinstance(task_run_id, UUID)

    lookup = await orion_client.read_task_run(task_run_id)
    assert isinstance(lookup, schemas.core.TaskRun)
    assert lookup.tags == list(bar.tags)
    assert lookup.task_key == bar.task_key
    assert lookup.empirical_policy == schemas.core.TaskRunPolicy(max_retries=3)
    assert lookup.state is None


async def test_create_then_read_task_run_with_state(orion_client):
    @flow
    def foo():
        pass

    @task(tags=["a", "b"], retries=3)
    def bar(orion_client):
        pass

    flow_run_id = await orion_client.create_flow_run(foo)
    task_run_id = await orion_client.create_task_run(
        bar, flow_run_id=flow_run_id, state=schemas.states.Running()
    )

    lookup = await orion_client.read_task_run(task_run_id)
    assert lookup.state.is_running()


async def test_set_then_read_task_run_state(orion_client):
    @flow
    def foo():
        pass

    @task
    def bar(orion_client):
        pass

    flow_run_id = await orion_client.create_flow_run(foo)
    task_run_id = await orion_client.create_task_run(bar, flow_run_id=flow_run_id)

    response = await orion_client.set_task_run_state(
        task_run_id,
        schemas.states.Completed(message="Test!"),
    )

    assert isinstance(response, OrchestrationResult)
    assert response.status == schemas.responses.SetStateStatus.ACCEPT

    run = await orion_client.read_task_run(task_run_id)
    assert isinstance(run.state, schemas.states.State)
    assert run.state.type == schemas.states.StateType.COMPLETED
    assert run.state.message == "Test!"


@dataclass
class ExDataClass:
    x: int


class ExPydanticModel(BaseModel):
    x: int


@pytest.mark.parametrize(
    "put_obj",
    [
        "hello",
        7,
        ExDataClass(x=1),
        ExPydanticModel(x=0),
    ],
)
async def test_put_then_retrieve_object(put_obj, orion_client):
    datadoc = await orion_client.persist_object(put_obj)
    assert datadoc.encoding == "orion"
    retrieved_obj = await orion_client.retrieve_object(datadoc)
    assert retrieved_obj == put_obj


async def test_client_non_async_with_is_helpful():
    with pytest.raises(RuntimeError, match="must be entered with an async context"):
        with OrionClient():
            pass
