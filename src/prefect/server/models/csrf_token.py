import secrets
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect import settings
from prefect.server.database import orm_models
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.schemas import core


@db_injector
async def create_or_update_csrf_token(
    db: PrefectDBInterface,
    session: AsyncSession,
    client: str,
) -> core.CsrfToken:
    """Create or update a CSRF token for a client. If the client already has a
    token, it will be updated.

    Args:
        session (AsyncSession): The database session
        client (str): The client identifier

    Returns:
        core.CsrfToken: The CSRF token
    """

    expiration = (
        datetime.now(timezone.utc)
        + settings.PREFECT_SERVER_CSRF_TOKEN_EXPIRATION.value()
    )
    token = secrets.token_hex(32)

    await session.execute(
        db.insert(orm_models.CsrfToken)
        .values(
            client=client,
            token=token,
            expiration=expiration,
        )
        .on_conflict_do_update(
            index_elements=[orm_models.CsrfToken.client],
            set_={"token": token, "expiration": expiration},
        ),
    )

    # Return the created / updated token object
    csrf_token = await read_token_for_client(session=session, client=client)
    assert csrf_token

    return csrf_token


async def read_token_for_client(
    session: AsyncSession,
    client: str,
) -> Optional[core.CsrfToken]:
    """Read a CSRF token for a client.

    Args:
        session (AsyncSession): The database session
        client (str): The client identifier

    Returns:
        Optional[core.CsrfToken]: The CSRF token, if it exists and is not
            expired.
    """
    token = (
        await session.execute(
            sa.select(orm_models.CsrfToken).where(
                sa.and_(
                    orm_models.CsrfToken.expiration > datetime.now(timezone.utc),
                    orm_models.CsrfToken.client == client,
                )
            )
        )
    ).scalar_one_or_none()

    if token is None:
        return None

    return core.CsrfToken.model_validate(token, from_attributes=True)


async def delete_expired_tokens(session: AsyncSession) -> int:
    """Delete expired CSRF tokens.

    Args:
        session (AsyncSession): The database session

    Returns:
        int: The number of tokens deleted
    """

    result = await session.execute(
        sa.delete(orm_models.CsrfToken).where(
            orm_models.CsrfToken.expiration < datetime.now(timezone.utc)
        )
    )
    return result.rowcount
