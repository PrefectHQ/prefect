import pytest
from uuid import uuid4


class TestCreateFlow:
    async def test_create_flow(self, client):
        flow_data = {"name": "my-flow"}
        response = await client.post("/flows/", json=flow_data)
        assert response.status_code == 200
        assert response.json()["name"] == "my-flow"


class TestReadFlow:
    async def test_read_flow(self, client):
        # first create a flow to read
        flow_data = {"name": "my-flow"}
        response = await client.post("/flows/", json=flow_data)
        assert response.status_code == 200
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
        for i in range(2):
            response = await client.post("/flows/", json={"name": f"my-flow-{i}"})
            assert response.status_code == 200

    async def test_read_flows(self, flows, client):
        response = await client.get("/flows/")
        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_read_flows_applies_limit(self, flows, client):
        response = await client.get("/flows/?limit=1")
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_read_flows_offset(self, flows, client):
        # right now this works because flows are ordered by name
        # by default, when ordering is actually implemented, this test
        # should be re-written
        response = await client.get("/flows/?offset=1")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["name"] == "my-flow-1"

    async def test_read_flows_returns_empty_list(self, client):
        response = await client.get("/flows/")
        assert response.status_code == 200
        assert response.json() == []


class TestDeleteFlow:
    async def test_delete_flow(self, client):
        # first create a flow to delete
        flow_data = {"name": "my-flow"}
        response = await client.post("/flows/", json=flow_data)
        assert response.status_code == 200
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
