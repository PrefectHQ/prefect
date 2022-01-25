async def test_validation_error_handler(client):
    bad_flow_data = {"name": "my-flow", "tags": "this should be a list not a string"}
    response = await client.post("/flows/", json=bad_flow_data)
    assert response.status_code == 422
    assert response.json()["exception_message"] == "Invalid request received."
    assert response.json()["exception_detail"] == [
        {
            "loc": ["body", "tags"],
            "msg": "value is not a valid list",
            "type": "type_error.list",
        }
    ]
    assert response.json()["request_body"] == bad_flow_data


async def test_health_check_route(client):
    response = await client.get("/health")
    assert response.status_code == 200
