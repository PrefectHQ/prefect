import secrets
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect import settings
from prefect.server.database.dependencies import inject_db
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.schemas import core


@inject_db
async def create_or_update_csrf_token(
    db: PrefectDBInterface,
    session: AsyncSession,
    client: str,
) -> core.CsrfToken:
    expiration = (
        datetime.now(timezone.utc)
        + settings.PREFECT_SERVER_CSRF_TOKEN_EXPIRATION.value()
    )
    token = secrets.token_hex(32)

    # Try to update the token if it already exists
    result = await session.execute(
        sa.update(db.CsrfToken)
        .where(db.CsrfToken.client == client)
        .values(token=token, expiration=expiration)
    )

    if result.rowcount < 1:
        # Client does not have a token, create a new one
        model = db.CsrfToken(
            client=client,
            token=token,
            expiration=expiration,
        )
        session.add(model)
        await session.flush()
        return core.CsrfToken.from_orm(model)
    else:
        # Return the updated token object
        return await read_token_for_client(session=session, client=client)


@inject_db
async def read_token_for_client(
    db: PrefectDBInterface,
    session: AsyncSession,
    client: str,
) -> Optional[core.CsrfToken]:
    token = (
        await session.execute(
            sa.select(db.CsrfToken).where(db.CsrfToken.client == client)
        )
    ).scalar_one_or_none()

    if token is None:
        return None

    return core.CsrfToken.from_orm(token)


@inject_db
async def delete_expired_tokens(db: PrefectDBInterface, session: AsyncSession) -> int:
    result = await session.execute(
        sa.delete(db.CsrfToken).where(
            db.CsrfToken.expiration < datetime.now(timezone.utc)
        )
    )
    return result.rowcount
