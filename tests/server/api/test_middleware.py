from datetime import datetime, timedelta, timezone

import httpx
import pytest
import sqlalchemy as sa
from fastapi import FastAPI, status
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.api.middleware import CsrfMiddleware
from prefect.server.database import PrefectDBInterface
from prefect.settings import (
    PREFECT_SERVER_CSRF_PROTECTION_ENABLED,
    temporary_settings,
)

app = FastAPI()
app.add_middleware(CsrfMiddleware)


@app.get("/")
@app.post("/")
@app.put("/")
@app.patch("/")
@app.delete("/")
async def hello():
    return {"message": "Hello World"}


@pytest.fixture
async def client():
    """
    Yield a test client for testing the api
    """
    global app
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="https://test"
    ) as async_client:
        yield async_client


@pytest.fixture(autouse=True)
def enable_csrf_protection():
    with temporary_settings({PREFECT_SERVER_CSRF_PROTECTION_ENABLED: True}):
        yield


@pytest.fixture
async def csrf_token(session: AsyncSession) -> schemas.core.CsrfToken:
    token = await models.csrf_token.create_or_update_csrf_token(
        session=session, client="client123"
    )
    await session.commit()
    return token


@pytest.mark.parametrize("enabled", [True, False])
async def test_csrf_get_pass_through(enabled: bool, client: httpx.AsyncClient):
    with temporary_settings({PREFECT_SERVER_CSRF_PROTECTION_ENABLED: enabled}):
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "Hello World"}


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
async def test_csrf_change_request_pass_through_disabled(
    method: str, client: httpx.AsyncClient
):
    with temporary_settings({PREFECT_SERVER_CSRF_PROTECTION_ENABLED: False}):
        response = await getattr(client, method)("/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "Hello World"}


async def test_csrf_403_no_token_or_client(client: httpx.AsyncClient):
    response = await client.post("/")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "Missing CSRF token."}


async def test_csrf_403_no_client(
    client: httpx.AsyncClient, csrf_token: schemas.core.CsrfToken
):
    response = await client.post("/", headers={"Prefect-Csrf-Token": csrf_token.token})
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "Missing client identifier."}


async def test_csrf_403_no_token(
    client: httpx.AsyncClient, csrf_token: schemas.core.CsrfToken
):
    response = await client.post(
        "/", headers={"Prefect-Csrf-Client": csrf_token.client}
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "Missing CSRF token."}


async def test_csrf_403_incorrect_token(
    client: httpx.AsyncClient, csrf_token: schemas.core.CsrfToken
):
    response = await client.post(
        "/",
        headers={
            "Prefect-Csrf-Token": "incorrect-token",
            "Prefect-Csrf-Client": csrf_token.client,
        },
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "Invalid CSRF token or client identifier."}


async def test_csrf_403_expired_token(
    db: PrefectDBInterface,
    session: AsyncSession,
    client: httpx.AsyncClient,
    csrf_token: schemas.core.CsrfToken,
):
    # Make the token expired
    await session.execute(
        sa.update(db.CsrfToken)
        .where(db.CsrfToken.client == csrf_token.client)
        .values(expiration=datetime.now(timezone.utc) - timedelta(days=1))
    )
    await session.commit()

    response = await client.post(
        "/",
        headers={
            "Prefect-Csrf-Token": csrf_token.token,
            "Prefect-Csrf-Client": csrf_token.client,
        },
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "Invalid CSRF token or client identifier."}


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
async def test_csrf_pass_through_enabled_valid_headers(
    method: str, client: httpx.AsyncClient, csrf_token: schemas.core.CsrfToken
):
    response = await getattr(client, method)(
        "/",
        headers={
            "Prefect-Csrf-Token": csrf_token.token,
            "Prefect-Csrf-Client": csrf_token.client,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "Hello World"}
