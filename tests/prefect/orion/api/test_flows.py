class TestCreateFlow:
    async def test_create_flow(self, client):
        flow_data = {"name": "my-flow"}
        response = await client.post("/flows/", json=flow_data)
        assert response.status_code == 200
        assert response.json()["name"] == "my-flow"
