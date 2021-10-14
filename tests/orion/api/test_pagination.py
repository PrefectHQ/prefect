from httpx import AsyncClient
import pytest
from fastapi import FastAPI, Body

from prefect import settings


@pytest.fixture
def app():
    return FastAPI()


@pytest.fixture
async def client(app):
    async with AsyncClient(app=app, base_url="http://test/") as async_client:
        yield async_client


class TestPagination:
    @pytest.fixture(autouse=True)
    def create_app_route(self, app):
        @app.post("/")
        def get_results(
            limit: int = Body(
                settings.orion.api.default_limit,
                ge=0,
                le=settings.orion.api.default_limit,
            ),
            offset: int = Body(0, ge=0),
        ):
            return {"limit": limit, "offset": offset}

    async def test_pagination_defaults(self, client):
        response = await client.post("/")
        assert response.status_code == 200
        assert response.json() == dict(limit=200, offset=0)

    async def test_negative_limit_not_allowed(self, client):
        response = await client.post("/", json=dict(limit=-1))
        assert response.status_code == 422
        assert "greater than or equal to 0" in response.text

    async def test_zero_limit(self, client):
        response = await client.post("/", json=dict(limit=0))
        assert response.status_code == 200
        assert response.json() == dict(limit=0, offset=0)

    async def test_too_large_limit(self, client):
        response = await client.post("/", json=dict(limit=1000))
        assert response.status_code == 422
        assert "less than or equal to 200" in response.text

    async def test_negative_offset_not_allowed(self, client):
        response = await client.post("/", json=dict(offset=-1))
        assert response.status_code == 422
        assert "greater than or equal to 0" in response.text
