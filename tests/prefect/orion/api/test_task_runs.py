import uuid
import pytest
from uuid import uuid4
from prefect.orion import models


class TestCreateTaskRun:
    async def test_create_task_run(self, flow_run, client, database_session):
        task_run_data = {"flow_run_id": flow_run.id, "task_key": "my-task-key"}
        response = await client.post("/task_runs/", json=task_run_data)
        assert response.status_code == 200
        assert response.json()["flow_run_id"] == flow_run.id
        assert response.json()["id"]

        task_run = await models.task_runs.read_task_run(
            session=database_session, task_run_id=response.json()["id"]
        )
        assert task_run.flow_run_id == flow_run.id


class TestReadTaskRun:
    async def test_read_task_run(self, flow_run, task_run, client):
        # make sure we we can read the task run correctly
        response = await client.get(f"/task_runs/{task_run.id}")
        assert response.status_code == 200
        assert response.json()["id"] == task_run.id
        assert response.json()["flow_run_id"] == flow_run.id

    async def test_read_task_run_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/task_runs/{uuid4()}")
        assert response.status_code == 404


class TestReadTaskRuns:
    async def test_read_task_runs(self, flow_run, task_run, client):
        response = await client.get(f"/task_runs/?flow_run_id={flow_run.id}")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == task_run.id
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
