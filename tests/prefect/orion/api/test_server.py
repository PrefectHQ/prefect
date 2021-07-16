async def test_hello_world(client):
    response = await client.get("/hello")
    assert response.status_code == 200
    assert response.json() == "👋"
