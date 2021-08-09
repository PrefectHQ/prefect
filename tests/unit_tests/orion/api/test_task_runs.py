import uuid
import pytest
from uuid import uuid4
from prefect.orion import models
from prefect.orion.schemas import states
import sqlalchemy as sa


class TestCreateTaskRun:
    async def test_create_task_run(self, flow_run, client, database_session):
        task_run_data = {"flow_run_id": str(flow_run.id), "task_key": "my-task-key"}
        response = await client.post("/task_runs/", json=task_run_data)
        assert response.status_code == 201
        assert response.json()["flow_run_id"] == str(flow_run.id)
        assert response.json()["id"]

        task_run = await models.task_runs.read_task_run(
            session=database_session, task_run_id=response.json()["id"]
        )
        assert task_run.flow_run_id == flow_run.id

    async def test_create_task_run_gracefully_upserts(
        self, flow_run, client, database_session
    ):
        # create a task run
        task_run_data = {
            "flow_run_id": str(flow_run.id),
            "task_key": "my-task-key",
            "dynamic_key": "my-dynamic-key",
        }
        task_run_response = await client.post("/task_runs/", json=task_run_data)

        # recreate the same task run, ensure graceful upsert
        response = await client.post("/task_runs/", json=task_run_data)
        assert response.status_code == 200
        assert response.json()["id"] == task_run_response.json()["id"]


class TestReadTaskRun:
    async def test_read_task_run(self, flow_run, task_run, client):
        # make sure we we can read the task run correctly
        response = await client.get(f"/task_runs/{task_run.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(task_run.id)
        assert response.json()["flow_run_id"] == str(flow_run.id)

    async def test_read_task_run_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/task_runs/{uuid4()}")
        assert response.status_code == 404


class TestReadTaskRuns:
    async def test_read_task_runs(self, flow_run, task_run, client):
        response = await client.get(f"/task_runs/?flow_run_id={flow_run.id}")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(task_run.id)
        assert response.json()[0]["flow_run_id"] == str(task_run.flow_run_id)

    async def test_read_task_runs_filters_by_flow_run_id(self, client):
        response = await client.get(f"/task_runs/?flow_run_id={uuid4()}")
        assert response.status_code == 200
        assert response.json() == []


class TestDeleteTaskRuns:
    async def test_delete_task_runs(self, task_run, client, database_session):
        # delete the task run
        response = await client.delete(f"/task_runs/{task_run.id}")
        assert response.status_code == 204

        # make sure it's deleted
        run = await models.task_runs.read_task_run(
            session=database_session, task_run_id=task_run.id
        )
        assert run is None
        response = await client.get(f"/task_runs/{task_run.id}")
        assert response.status_code == 404

    async def test_delete_task_run_returns_404_if_does_not_exist(self, client):
        response = await client.delete(f"/task_runs/{uuid4()}")
        assert response.status_code == 404


class TestSetTaskRunState:
    async def test_set_task_run_state(self, task_run, client, database_session):
        response = await client.post(
            f"/task_runs/{task_run.id}/set_state",
            json=dict(type="RUNNING", name="Test State"),
        )
        assert response.status_code == 201
        assert response.json()["status"] == "ACCEPT"
        assert response.json()["new_state"] is None
        assert response.json()["run_details"]["run_count"] == 1

        run = await models.task_runs.read_task_run(
            session=database_session, task_run_id=task_run.id
        )
        assert run.state.type.value == "RUNNING"
        assert run.state.name == "Test State"

    async def test_failed_becomes_awaiting_retry(
        self, task_run, client, database_session
    ):
        # set max retries to 1
        # copy to trigger ORM updates
        task_run.empirical_policy = task_run.empirical_policy.copy()
        task_run.empirical_policy.max_retries = 1
        await database_session.flush()

        await models.task_run_states.create_task_run_state(
            session=database_session,
            task_run_id=task_run.id,
            state=states.State(type="RUNNING"),
        )

        # fail the running task run
        response = await client.post(
            f"/task_runs/{task_run.id}/set_state",
            json=dict(type="FAILED"),
        )
        assert response.status_code == 201
        assert response.json()["status"] == "REJECT"
        new_state = states.State(**response.json()["new_state"])
        assert new_state.name == "Awaiting Retry"
        assert new_state.type == states.StateType.SCHEDULED
