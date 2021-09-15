from uuid import uuid4, UUID

import pendulum
import pydantic
import pytest

from prefect.orion import models, schemas


class TestCreateFlow:
    async def test_create_flow(self, session, client):
        flow_data = {"name": "my-flow"}
        response = await client.post("/flows/", json=flow_data)
        assert response.status_code == 201
        assert response.json()["name"] == "my-flow"
        flow_id = response.json()["id"]

        flow = await models.flows.read_flow(session=session, flow_id=flow_id)
        assert str(flow.id) == flow_id

    async def test_create_flow_populates_and_returned_created(self, client):
        now = pendulum.now(tz="UTC")
        flow_data = {"name": "my-flow"}
        response = await client.post("/flows/", json=flow_data)
        assert response.status_code == 201
        assert response.json()["name"] == "my-flow"
        assert pendulum.parse(response.json()["created"]) >= now
        assert pendulum.parse(response.json()["updated"]) >= now

    async def test_create_flow_gracefully_fallsback(self, client):
        """If the flow already exists, we return a 200 code"""
        flow_data = {"name": "my-flow"}
        response_1 = await client.post("/flows/", json=flow_data)
        response_2 = await client.post("/flows/", json=flow_data)
        assert response_2.status_code == 200
        assert response_2.json()["name"] == "my-flow"


class TestUpdateFlow:
    async def test_update_flow_succeeds(self, session, client):
        flow = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        await session.commit()
        now = pendulum.now("UTC")

        response = await client.patch(
            f"/flows/{str(flow.id)}",
            json=schemas.actions.FlowUpdate(tags=["TB12"]).dict(),
        )
        assert response.status_code == 200
        updated_flow = pydantic.parse_obj_as(schemas.core.Flow, response.json())
        assert updated_flow.tags == ["TB12"]
        assert updated_flow.updated > now

    async def test_update_flow_does_not_update_if_fields_not_set(self, session, client):
        flow = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        await session.commit()

        response = await client.patch(
            f"/flows/{str(flow.id)}",
            json={},
        )
        assert response.status_code == 200
        updated_flow = pydantic.parse_obj_as(schemas.core.Flow, response.json())
        assert updated_flow.tags == ["db", "blue"]

    async def test_update_flow_rasises_error_if_flow_does_not_exist(self, client):
        response = await client.patch(
            f"/flows/{str(uuid4())}",
            json={},
        )
        assert response.status_code == 404


class TestReadFlow:
    async def test_read_flow(self, client):
        # first create a flow to read
        flow_data = {"name": "my-flow"}
        response = await client.post("/flows/", json=flow_data)
        flow_id = response.json()["id"]

        # make sure we we can read the flow correctly
        response = await client.get(f"/flows/{flow_id}")
        assert response.status_code == 200
        assert response.json()["id"] == flow_id
        assert response.json()["name"] == "my-flow"

    async def test_read_flow_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/flows/{uuid4()}")
        assert response.status_code == 404


class TestReadFlows:
    @pytest.fixture
    async def flows(self, client):
        await client.post("/flows/", json={"name": f"my-flow-1"})
        await client.post("/flows/", json={"name": f"my-flow-2"})

    async def test_read_flows(self, flows, client):
        response = await client.get("/flows/")
        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_read_flows_applies_limit(self, flows, client):
        response = await client.get("/flows/", params=dict(limit=1))
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_read_flows_applies_flow_filter(self, client, session):
        flow_1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        flow_2 = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-2", tags=["db"])
        )
        await session.commit()

        flow_filter = {"flows": {"names": ["my-flow-1"]}}
        response = await client.get("/flows/", json=flow_filter)
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert UUID(response.json()[0]["id"]) == flow_1.id

    async def test_read_flows_applies_flow_run_filter(self, client, session):
        flow_1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        flow_2 = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-2", tags=["db"])
        )
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow_1.id),
        )
        await session.commit()

        flow_filter = {"flow_runs": {"ids": [str(flow_run_1.id)]}}
        response = await client.get("/flows/", json=flow_filter)
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert UUID(response.json()[0]["id"]) == flow_1.id

    async def test_read_flows_applies_task_run_filter(self, client, session):
        flow_1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        flow_2 = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-2", tags=["db"])
        )
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow_1.id),
        )
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=flow_run_1.id, task_key="my-key"
            ),
        )
        await session.commit()

        flow_filter = {"task_runs": {"ids": [str(task_run_1.id)]}}
        response = await client.get("/flows/", json=flow_filter)
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert UUID(response.json()[0]["id"]) == flow_1.id

    async def test_read_flows_offset(self, flows, client):
        # right now this works because flows are ordered by name
        # by default, when ordering is actually implemented, this test
        # should be re-written
        response = await client.get("/flows/", params=dict(offset=1))
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["name"] == "my-flow-2"

    async def test_read_flows_returns_empty_list(self, client):
        response = await client.get("/flows/")
        assert response.status_code == 200
        assert response.json() == []


class TestDeleteFlow:
    async def test_delete_flow(self, client):
        # first create a flow to delete
        flow_data = {"name": "my-flow"}
        response = await client.post("/flows/", json=flow_data)
        flow_id = response.json()["id"]

        # delete the flow
        response = await client.delete(f"/flows/{flow_id}")
        assert response.status_code == 204

        # make sure it's deleted
        response = await client.get(f"/flows/{flow_id}")
        assert response.status_code == 404

    async def test_delete_flow_returns_404_if_does_not_exist(self, client):
        response = await client.delete(f"/flows/{uuid4()}")
        assert response.status_code == 404
