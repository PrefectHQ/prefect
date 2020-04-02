# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import datetime
import pendulum
import pytest

import prefect

import prefect_server
from prefect_server import api
from prefect_server.database import models


@pytest.fixture
async def db_flow_id():
    """
    A minimal, controlled flow for use in testing the flow run -> task run
    creation trigger
    """
    flow = prefect.Flow(name="Test Flow")
    flow.add_task(prefect.Task("task-1", cache_key="my-key-1"))
    flow.add_task(prefect.Task("task-2", cache_key="my-key-2"))
    flow_id = await api.flows.create_flow(serialized_flow=flow.serialize())
    return flow_id


class TestFlowRunInsertTrigger:
    async def test_insert_flow_run_creates_task_runs(self, db_flow_id):
        # create a flow run
        flow_run_id = await models.FlowRun(flow_id=db_flow_id,).insert()
        # retrieve the task runs associated with the flow run
        task_runs = await models.TaskRun.where(
            {"flow_run_id": {"_eq": flow_run_id}}
        ).get({"id", "flow_run_id", "task_id", "cache_key", "map_index"})
        tasks = await models.Task.where({"flow_id": {"_eq": db_flow_id}}).get(
            {"id", "cache_key"}
        )
        # confirm we have two task runs
        assert len(task_runs) == 2
        # confirm that each of them looks as we'd expect
        assert task_runs[0].flow_run_id == flow_run_id
        assert task_runs[1].flow_run_id == flow_run_id
        assert not set([task_run.task_id for task_run in task_runs]) - set(
            [task.id for task in tasks]
        )
        assert not set([task_run.cache_key for task_run in task_runs]) - set(
            [task.cache_key for task in tasks]
        )
        assert task_runs[0].map_index == -1
        assert task_runs[1].map_index == -1

    async def test_insert_flow_run_creates_task_run_states(self, db_flow_id):
        # create a flow run and get its task runs
        flow_run_id = await models.FlowRun(flow_id=db_flow_id).insert()
        task_runs = await models.TaskRun.where(
            {"flow_run_id": {"_eq": flow_run_id}}
        ).get({"id"})

        # confirm we have two task runs
        assert len(task_runs) == 2

        # confirm each task run state looks as we'd expect
        task_run_id_1 = task_runs[0].id
        task_run_id_2 = task_runs[1].id

        task_run_state_1 = await models.TaskRunState.where(
            {"task_run_id": {"_eq": task_run_id_1}}
        ).get({"task_run_id", "state", "message", "serialized_state"})
        # confirm the trigger only created one state
        assert len(task_run_state_1) == 1
        assert task_run_state_1[0].task_run_id == task_run_id_1
        assert task_run_state_1[0].state == "Pending"
        assert task_run_state_1[0].message == "Task run created"
        assert task_run_state_1[0].serialized_state == {
            "type": "Pending",
            "message": "Task run created",
        }

        # second verse, same as the first
        task_run_state_2 = await models.TaskRunState.where(
            {"task_run_id": {"_eq": task_run_id_2}}
        ).get({"task_run_id", "state", "message", "serialized_state"})
        assert len(task_run_state_2) == 1
        assert task_run_state_2[0].task_run_id == task_run_id_2
        assert task_run_state_2[0].state == "Pending"
        assert task_run_state_2[0].message == "Task run created"
        assert task_run_state_2[0].serialized_state == {
            "type": "Pending",
            "message": "Task run created",
        }
