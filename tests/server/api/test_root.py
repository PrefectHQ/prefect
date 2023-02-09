from fastapi import status


async def test_hello_world(client):
    response = await client.get("/hello")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "👋"
