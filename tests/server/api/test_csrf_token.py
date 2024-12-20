from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.database import PrefectDBInterface
from prefect.settings import PREFECT_SERVER_CSRF_PROTECTION_ENABLED, temporary_settings


@pytest.fixture(autouse=True)
def enable_csrf_protection():
    with temporary_settings({PREFECT_SERVER_CSRF_PROTECTION_ENABLED: True}):
        yield


async def test_can_get_csrf_token(client: AsyncClient, session: AsyncSession):
    response = await client.get("/csrf-token?client=client123")
    assert response.status_code == 200

    token = schemas.core.CsrfToken(**response.json())
    db_token = await models.csrf_token.read_token_for_client(
        session=session, client="client123"
    )

    assert db_token
    assert token.client == "client123"
    assert token.token == db_token.token


async def test_client_param_required(client: AsyncClient):
    response = await client.get("/csrf-token")
    assert response.status_code == 422
    assert response.json() == {
        "exception_detail": [
            {
                "input": None,
                "loc": ["query", "client"],
                "msg": "Field required",
                "type": "missing",
            }
        ],
        "exception_message": "Invalid request received.",
        "request_body": None,
    }


async def test_422_when_csrf_protection_disabled(client: AsyncClient):
    with temporary_settings({PREFECT_SERVER_CSRF_PROTECTION_ENABLED: False}):
        response = await client.get("/csrf-token?client=client123")
        assert response.status_code == 422
        assert response.json() == {"detail": "CSRF protection is disabled."}


async def test_deletes_expired_tokens(
    db: PrefectDBInterface, session: AsyncSession, client: AsyncClient
):
    # Create some tokens
    for i in range(5):
        await models.csrf_token.create_or_update_csrf_token(
            session=session, client=f"client{i}"
        )

    # Update some of them to be expired
    await session.execute(
        sa.update(db.CsrfToken)
        .where(db.CsrfToken.client.in_(["client0", "client1"]))
        .values(expiration=datetime.now(timezone.utc) - timedelta(days=1))
    )

    await session.commit()

    response = await client.get("/csrf-token?client=client123")
    assert response.status_code == 200

    all_tokens = (await session.execute(sa.select(db.CsrfToken))).scalars().all()

    # Five tokens were created upfront, one was created from the client.get
    # request, and two of those were expired. (5 + 1) - 2 = 4
    assert len(all_tokens) == 4

    assert "client0" not in [t.client for t in all_tokens]
    assert "client1" not in [t.client for t in all_tokens]
