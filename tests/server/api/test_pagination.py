import pytest
from fastapi import Body, FastAPI
from httpx import ASGITransport, AsyncClient

from prefect._internal.compatibility.starlette import status
from prefect.server.api.dependencies import LimitBody


@pytest.fixture
def app():
    return FastAPI()


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test/"
    ) as async_client:
        yield async_client


class TestPagination:
    @pytest.fixture(autouse=True)
    def create_app_route(self, app):
        @app.post("/")
        def get_results(
            limit: int = LimitBody(),
            offset: int = Body(0, ge=0),
        ):
            return {"limit": limit, "offset": offset}

    async def test_pagination_defaults(self, client):
        response = await client.post("/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == dict(limit=200, offset=0)

    async def test_negative_limit_not_allowed(self, client):
        response = await client.post("/", json=dict(limit=-1))
        assert response.status_code == 422
        assert "greater than or equal to 0" in response.text

    async def test_zero_limit(self, client):
        response = await client.post("/", json=dict(limit=0))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == dict(limit=0, offset=0)

    async def test_too_large_limit(self, client):
        response = await client.post("/", json=dict(limit=1000))
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "less than or equal to 200" in response.text

    async def test_negative_offset_not_allowed(self, client):
        response = await client.post("/", json=dict(offset=-1))
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "greater than or equal to 0" in response.text
