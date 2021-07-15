class TestCreateFlow:
    async def test_create_flow(self, test_client):
        flow_data = {
            "name": "my-flow"
        }
        response = await test_client.post(
            "/flows/",
            json=flow_data
        )
        assert response.status_code == 200
        assert response.json()["name"] == "my-flow"