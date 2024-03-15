from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas


async def test_can_get_csrf_token(client: AsyncClient, session: AsyncSession):
    response = await client.get("/csrf-token?client=client123")
    assert response.status_code == 200

    token = schemas.core.CsrfToken(**response.json())
    db_token = await models.csrf_token.read_token_for_client(
        session=session, client="client123"
    )

    assert token.client == "client123"
    assert token.token == db_token.token


async def test_client_param_required(client: AsyncClient):
    response = await client.get("/csrf-token")
    assert response.status_code == 422
    assert response.json() == {
        "exception_detail": [
            {
                "loc": ["query", "client"],
                "msg": "field required",
                "type": "value_error.missing",
            }
        ],
        "exception_message": "Invalid request received.",
        "request_body": None,
    }
