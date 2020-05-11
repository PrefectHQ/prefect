# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import datetime
import inspect
import uuid
import warnings
from box import Box

import pendulum
import pytest
from asynctest import CoroutineMock
from click.testing import CliRunner

import prefect
import prefect_server
from prefect.engine.state import Running, Submitted, Success
from prefect_server import api, config
from prefect_server.database import hasura, models
import sqlalchemy as sa


@pytest.fixture(scope="session")
def sqlalchemy_engine():
    return sa.create_engine(config.database.connection_url)


@pytest.fixture(autouse=True)
async def delete_data_after_each_test():
    try:
        yield
    finally:
        await models.Flow.where().delete()


@pytest.fixture
async def flow_id():
    flow = prefect.Flow(
        name="Test Flow",
        schedule=prefect.schedules.IntervalSchedule(
            start_date=pendulum.datetime(2018, 1, 1),
            interval=datetime.timedelta(days=1),
        ),
    )
    flow.add_edge(
        prefect.Task("t1", tags={"red", "blue"}),
        prefect.Task("t2", tags={"red", "green"}),
    )
    flow.add_task(prefect.Parameter("x", default=1))

    flow_id = await api.flows.create_flow(serialized_flow=flow.serialize())

    return flow_id


@pytest.fixture
async def labeled_flow_id():

    flow = prefect.Flow(
        name="Labeled Flow",
        environment=prefect.environments.execution.remote.RemoteEnvironment(
            labels=["foo", "bar"]
        ),
        schedule=prefect.schedules.IntervalSchedule(
            start_date=pendulum.datetime(2018, 1, 1),
            interval=datetime.timedelta(days=1),
        ),
    )
    flow.add_edge(
        prefect.Task("t1", tags={"red", "blue"}),
        prefect.Task("t2", tags={"red", "green"}),
    )
    flow.add_task(prefect.Parameter("x", default=1))

    flow_id = await api.flows.create_flow(serialized_flow=flow.serialize())
    return flow_id


@pytest.fixture
async def schedule_id(flow_id):
    schedule = await models.Schedule.where({"flow_id": {"_eq": flow_id}}).first("id")
    return schedule.id


@pytest.fixture
async def task_id(flow_id):
    task = await models.Task.where({"flow_id": {"_eq": flow_id}}).first("id")
    return task.id


@pytest.fixture
async def labeled_task_id(labeled_flow_id):
    task = await models.Task.where({"flow_id": {"_eq": labeled_flow_id}}).first("id")
    return task.id


@pytest.fixture
async def parameter_id(flow_id):
    task = await models.Task.where(
        {"flow_id": {"_eq": flow_id}, "type": {"_like": "%Parameter%"}}
    ).first("id")
    return task.id


@pytest.fixture
async def edge_id(flow_id):
    edge = await models.Edge.where({"flow_id": {"_eq": flow_id}}).first("id")
    return edge.id


@pytest.fixture
async def flow_run_id(flow_id):
    return await api.runs.create_flow_run(flow_id=flow_id, parameters=dict(x=1))


@pytest.fixture
async def running_flow_run_id(flow_run_id):
    await api.states.set_flow_run_state(flow_run_id, state=Running())
    return flow_run_id


@pytest.fixture
async def labeled_flow_run_id(labeled_flow_id):
    return await api.runs.create_flow_run(flow_id=labeled_flow_id, parameters=dict(x=1))


@pytest.fixture
async def flow_run_id_2(flow_id):
    """
    A flow run in a Running state
    """

    flow_run_id = await api.runs.create_flow_run(flow_id=flow_id, parameters=dict(x=1))
    await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=Running())
    return flow_run_id


@pytest.fixture
async def flow_run_id_3(flow_id):
    """
    A flow run in a Success state
    """
    flow_run_id = await api.runs.create_flow_run(flow_id=flow_id, parameters=dict(x=1))
    await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=Running())
    await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=Success())
    return flow_run_id


@pytest.fixture
async def task_run_id(flow_run_id, task_id):
    return await api.runs.get_or_create_task_run(
        flow_run_id=flow_run_id, task_id=task_id, map_index=None
    )


@pytest.fixture
async def labeled_task_run_id(labeled_flow_run_id, labeled_task_id):
    return await api.runs.get_or_create_task_run(
        flow_run_id=labeled_flow_run_id, task_id=labeled_task_id, map_index=None
    )


@pytest.fixture
async def task_run_id_2(flow_run_id_2, task_id):
    """
    A task run in a Running state
    """

    task_run_id = await api.runs.get_or_create_task_run(
        flow_run_id=flow_run_id_2, task_id=task_id, map_index=None
    )
    await api.states.set_task_run_state(task_run_id=task_run_id, state=Running())
    return task_run_id


@pytest.fixture
async def task_run_id_3(flow_run_id_3, task_id):
    """
    A task run in a Success state
    """
    task_run_id = await api.runs.get_or_create_task_run(
        flow_run_id=flow_run_id_3, task_id=task_id, map_index=None
    )

    await api.states.set_task_run_state(task_run_id=task_run_id, state=Success())
    return task_run_id


@pytest.fixture
async def excess_submitted_task_runs():

    parameters = {}
    # pump up the task counter by creating artificial task runs
    flow = prefect.Flow(
        name="Test Flow",
        schedule=prefect.schedules.IntervalSchedule(
            start_date=pendulum.datetime(2018, 1, 1),
            interval=datetime.timedelta(days=1),
        ),
    )
    for i in range(config.queued_runs_returned_limit):
        flow.add_task(prefect.Parameter(f"x{i}", default=1))
        parameters.update({f"x{i}": 1})

    flow_id = await api.flows.create_flow(serialized_flow=flow.serialize())

    flow_run = await api.runs.create_flow_run(flow_id=flow_id, parameters=parameters)
    tasks = await models.Task.where({"flow_id": {"_eq": flow_id}}).get("id")

    for task in tasks:
        task_run = await api.runs.get_or_create_task_run(
            flow_run_id=flow_run, task_id=task.id, map_index=None
        )
        await api.states.set_task_run_state(task_run_id=task_run, state=Submitted())
