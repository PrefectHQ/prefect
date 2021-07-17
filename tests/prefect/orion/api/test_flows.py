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

        # make surwe we can read the flow correctly
        response = await client.get(f"/flows/{flow_id}")
        assert response.status_code == 200
        assert response.json()["id"] == flow_id
        assert response.json()["name"] == "my-flow"

    async def test_read_flow_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/flows/{uuid4()}")
        assert response.status_code == 404
