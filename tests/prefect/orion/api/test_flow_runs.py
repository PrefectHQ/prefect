import pytest
from uuid import uuid4
from prefect.orion import models


class TestCreateFlowRun:
    async def test_create_flow_run(self, flow, client, database_session):
        flow_run_data = {"flow_id": flow.id, "flow_version": "0.1"}
        response = await client.post("/flow_runs/", json=flow_run_data)
        assert response.status_code == 200
        assert response.json()["flow_id"] == flow.id
        assert response.json()["flow_version"] == "0.1"
        assert response.json()["id"]

        flow_run = await models.flow_runs.read_flow_run(
            session=database_session, id=response.json()["id"]
        )
        assert flow_run.flow_id == flow.id


class TestReadFlowRun:
    async def test_read_flow_run(self, flow, flow_run, client):
        # make sure we we can read the flow run correctly
        response = await client.get(f"/flow_runs/{flow_run.id}")
        assert response.status_code == 200
        assert response.json()["id"] == flow_run.id
        assert response.json()["flow_id"] == flow.id

    async def test_read_flow_run_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/flow_runs/{uuid4()}")
        assert response.status_code == 404


class TestReadFlowRuns:
    @pytest.fixture
    async def flow_runs(self, client, flow):
        for i in range(2):
            flow_run_data = {"flow_id": flow.id, "flow_version": str(i)}
            response = await client.post("/flow_runs/", json=flow_run_data)
            assert response.status_code == 200

    async def test_read_flow_runs(self, flow_runs, client):
        response = await client.get("/flow_runs/")
        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_read_flow_runs_applies_limit(self, flow_runs, client):
        response = await client.get("/flow_runs/?limit=1")
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_read_flow_runs_returns_empty_list(self, client):
        response = await client.get("/flow_runs/")
        assert response.status_code == 200
        assert response.json() == []


class TestDeleteFlowRuns:
    async def test_delete_flow_runs(self, flow_run, client, database_session):
        # delete the flow run
        response = await client.delete(f"/flow_runs/{flow_run.id}")
        assert response.status_code == 204

        # make sure it's deleted
        run = await models.flow_runs.read_flow_run(
            session=database_session, id=flow_run.id
        )
        assert run is None
        response = await client.get(f"/flow_runs/{flow_run.id}")
        assert response.status_code == 404

    async def test_delete_flow_run_returns_404_if_does_not_exist(self, client):
        response = await client.delete(f"/flow_runs/{uuid4()}")
        assert response.status_code == 404
