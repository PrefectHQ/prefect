import sqlalchemy as sa
import pytest
from uuid import uuid4
from prefect.orion import models
from prefect.orion.schemas import responses, states, actions


class TestCreateFlowRun:
    async def test_create_flow_run(self, flow, client, database_session):
        flow_run_data = {"flow_id": str(flow.id)}
        response = await client.post("/flow_runs/", json=flow_run_data)
        assert response.status_code == 201
        assert response.json()["flow_id"] == str(flow.id)
        assert response.json()["id"]

        flow_run = await models.flow_runs.read_flow_run(
            session=database_session, flow_run_id=response.json()["id"]
        )
        assert flow_run.flow_id == flow.id

    async def test_create_multiple_flow_runs(self, flow, client, database_session):
        response1 = await client.post("/flow_runs/", json={"flow_id": str(flow.id)})
        response2 = await client.post("/flow_runs/", json={"flow_id": str(flow.id)})
        assert response1.status_code == 201
        assert response2.status_code == 201
        assert response1.json()["flow_id"] == str(flow.id)
        assert response2.json()["flow_id"] == str(flow.id)
        assert response1.json()["id"] != response2.json()["id"]

        result = await database_session.execute(
            sa.select(models.orm.FlowRun.id).filter_by(flow_id=flow.id)
        )
        ids = result.scalars().all()
        assert {response1.json()["id"], response2.json()["id"]} == {str(i) for i in ids}

    async def test_create_flow_run_with_idempotency_key_recovers_original_flow_run(
        self, flow, client, database_session
    ):
        flow_run_data = {"flow_id": str(flow.id), "idempotency_key": "test-key"}
        response1 = await client.post("/flow_runs/", json=flow_run_data)
        assert response1.status_code == 201

        response2 = await client.post("/flow_runs/", json=flow_run_data)
        assert response2.status_code == 200
        assert response1.json()["id"] == response2.json()["id"]

    async def test_create_flow_run_with_idempotency_key_across_multiple_flows(
        self, flow, client, database_session
    ):
        flow2 = models.orm.Flow(name="another flow")
        database_session.add(flow2)
        await database_session.flush()

        response1 = await client.post(
            "/flow_runs/", json={"flow_id": str(flow.id), "idempotency_key": "test-key"}
        )
        assert response1.status_code == 201

        response2 = await client.post(
            "/flow_runs/",
            json={"flow_id": str(flow2.id), "idempotency_key": "test-key"},
        )
        assert response2.status_code == 201
        assert response1.json()["id"] != response2.json()["id"]

    async def test_create_flow_run_with_provided_id(
        self, flow, client, database_session
    ):
        flow_run_data = dict(flow_id=str(flow.id), id=str(uuid4()), flow_version="0.1")
        response = await client.post("/flow_runs/", json=flow_run_data)
        assert response.json()["id"] == flow_run_data["id"]

        flow_run = await models.flow_runs.read_flow_run(
            session=database_session, flow_run_id=flow_run_data["id"]
        )
        assert flow_run

    async def test_create_flow_run_with_subflow_information(
        self, flow, task_run, client, database_session
    ):
        flow_run_data = dict(
            flow_id=str(flow.id),
            parent_task_run_id=str(task_run.id),
            flow_version="0.1",
        )
        response = await client.post("/flow_runs/", json=flow_run_data)

        flow_run = await models.flow_runs.read_flow_run(
            session=database_session, flow_run_id=response.json()["id"]
        )
        assert flow_run.parent_task_run_id == task_run.id


class TestReadFlowRun:
    async def test_read_flow_run(self, flow, flow_run, client):
        # make sure we we can read the flow run correctly
        response = await client.get(f"/flow_runs/{flow_run.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(flow_run.id)
        assert response.json()["flow_id"] == str(flow.id)

    async def test_read_flow_run_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/flow_runs/{uuid4()}")
        assert response.status_code == 404


class TestReadFlowRuns:
    @pytest.fixture
    async def flow_runs(self, flow, database_session):
        flow_2 = await models.flows.create_flow(
            session=database_session,
            flow=actions.FlowCreate(name="another-test"),
        )

        flow_run_1 = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=actions.FlowRunCreate(flow_id=flow.id),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=actions.FlowRunCreate(flow_id=flow.id),
        )
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=actions.FlowRunCreate(flow_id=flow_2.id),
        )
        return [flow_run_1, flow_run_2, flow_run_3]

    async def test_read_flow_runs(self, flow_runs, client):
        response = await client.get("/flow_runs/")
        assert response.status_code == 200
        assert len(response.json()) == 3

    async def test_read_flow_runs(self, flow, flow_runs, client):
        response = await client.get("/flow_runs/", params=dict(flow_id=flow.id))
        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_read_flow_runs_applies_limit(self, flow_runs, client):
        response = await client.get("/flow_runs/", params=dict(limit=1))
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
            session=database_session, flow_run_id=flow_run.id
        )
        assert run is None
        response = await client.get(f"/flow_runs/{flow_run.id}")
        assert response.status_code == 404

    async def test_delete_flow_run_returns_404_if_does_not_exist(self, client):
        response = await client.delete(f"/flow_runs/{uuid4()}")
        assert response.status_code == 404


class TestSetFlowRunState:
    async def test_set_flow_run_state(self, flow_run, client, database_session):
        response = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(type="RUNNING", name="Test State"),
        )
        assert response.status_code == 201

        api_response = responses.SetStateResponse.parse_obj(response.json())
        assert api_response.status == responses.SetStateStatus.ACCEPT

        run = await models.flow_runs.read_flow_run(
            session=database_session, flow_run_id=flow_run.id
        )
        assert run.state.type == states.StateType.RUNNING
        assert run.state.name == "Test State"
