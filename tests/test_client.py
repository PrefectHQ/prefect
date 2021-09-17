from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

import pendulum
import pytest
from pydantic import BaseModel

from prefect import flow
from prefect import orion
from prefect.client import OrionClient
from prefect.orion import schemas
from prefect.orion.orchestration.rules import OrchestrationResult
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import Scheduled, Pending, Running, StateType
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


async def test_read_flow_runs_without_filter(orion_client):
    @flow(tags=["a", "b"])
    def foo():
        pass

    fr_id_1 = await orion_client.create_flow_run(foo)
    fr_id_2 = await orion_client.create_flow_run(foo)

    flows = await orion_client.read_flow_runs()
    assert len(flows) == 2
    assert all(isinstance(flow, schemas.core.FlowRun) for flow in flows)
    assert {flow.id for flow in flows} == {fr_id_1, fr_id_2}


async def test_read_flow_runs_with_filtering(orion_client):
    @flow
    def foo():
        pass

    @flow
    def bar():
        pass

    fr_id_1 = await orion_client.create_flow_run(foo, state=Pending())
    fr_id_2 = await orion_client.create_flow_run(foo, state=Scheduled())
    fr_id_3 = await orion_client.create_flow_run(bar, state=Pending())
    # Only below should match the filter
    fr_id_4 = await orion_client.create_flow_run(bar, state=Scheduled())
    fr_id_5 = await orion_client.create_flow_run(bar, state=Running())

    flows = await orion_client.read_flow_runs(
        flows=schemas.filters.FlowFilter(names=["bar"]),
        flow_runs=schemas.filters.FlowRunFilter(
            states=[
                StateType.SCHEDULED,
                StateType.RUNNING,
            ]
        ),
    )
    assert len(flows) == 2
    assert all(isinstance(flow, schemas.core.FlowRun) for flow in flows)
    assert {flow.id for flow in flows} == {fr_id_4, fr_id_5}


async def test_read_flows_without_filter(orion_client):
    @flow
    def foo():
        pass

    @flow
    def bar():
        pass

    flow_id_1 = await orion_client.create_flow(foo)
    flow_id_2 = await orion_client.create_flow(bar)

    flows = await orion_client.read_flows()
    assert len(flows) == 2
    assert all(isinstance(flow, schemas.core.Flow) for flow in flows)
    assert {flow.id for flow in flows} == {flow_id_1, flow_id_2}


async def test_read_flows_with_filter(orion_client):
    @flow
    def foo():
        pass

    @flow
    def bar():
        pass

    @flow
    def foobar():
        pass

    flow_id_1 = await orion_client.create_flow(foo)
    flow_id_2 = await orion_client.create_flow(bar)
    flow_id_3 = await orion_client.create_flow(foobar)

    flows = await orion_client.read_flows(
        flows=schemas.filters.FlowFilter(names=["foo", "bar"])
    )
    assert len(flows) == 2
    assert all(isinstance(flow, schemas.core.Flow) for flow in flows)
    assert {flow.id for flow in flows} == {flow_id_1, flow_id_2}


async def test_create_flow_run_from_deployment(orion_client, deployment):
    flow_run_id = await orion_client.create_flow_run_from_deployment(deployment)
    flow_run = await orion_client.read_flow_run(flow_run_id)
    # Deployment details attached
    assert flow_run.deployment_id == deployment.id
    assert flow_run.flow_id == deployment.flow_id
    # Flow version is not populated yet
    assert flow_run.flow_version is None
    # State is scheduled for now
    assert flow_run.state.type == schemas.states.StateType.SCHEDULED
    assert (
        pendulum.now("utc")
        .diff(flow_run.state.state_details.scheduled_time)
        .in_seconds()
        < 1
    )


async def test_update_flow_run(orion_client):
    @flow
    def foo():
        pass

    flow_run_id = await orion_client.create_flow_run(foo)
    flow_run = await orion_client.read_flow_run(flow_run_id)

    # No mutation for unset fields
    await orion_client.update_flow_run(flow_run_id)
    unchanged_flow_run = await orion_client.read_flow_run(flow_run_id)
    assert unchanged_flow_run == flow_run

    # Fields updated when set
    await orion_client.update_flow_run(
        flow_run_id, flow_version="foo", parameters={"foo": "bar"}
    )
    updated_flow_run = await orion_client.read_flow_run(flow_run_id)
    assert updated_flow_run.flow_version == "foo"
    assert updated_flow_run.parameters == {"foo": "bar"}


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
