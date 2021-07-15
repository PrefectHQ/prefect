async def test_hello_world(test_client):
    response = await test_client.get("/hello")
    assert response.status_code == 200
    assert response.json() == "👋"
