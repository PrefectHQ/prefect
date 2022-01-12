"""
Functions for interacting with concurrency limit ORM objects.
Intended for internal use by the Orion API.
"""

import sqlalchemy as sa
from uuid import UUID

from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


@inject_db
async def create_concurrency_limit(
    session: sa.orm.Session,
    concurrency_limit: schemas.core.ConcurrencyLimit,
    db: OrionDBInterface,
):
    insert_values = concurrency_limit.dict(shallow=True, exclude_unset=True)
    concurrency_tag = insert_values["tag"]

    insert_stmt = (await db.insert(db.ConcurrencyLimit)).values(**insert_values)

    await session.execute(insert_stmt)

    query = sa.select(db.ConcurrencyLimit).where(
        db.ConcurrencyLimit.tag == concurrency_tag
    )

    result = await session.execute(query)
    return result.scalar()


@inject_db
async def read_concurrency_limit(
    session: sa.orm.Session,
    concurrency_limit_id: UUID,
    db: OrionDBInterface,
):
    return await session.get(db.ConcurrencyLimit, concurrency_limit_id)


@inject_db
async def read_concurrency_limit_by_tag(
    session: sa.orm.Session,
    tag: str,
    db: OrionDBInterface,
):
    query = sa.select(db.ConcurrencyLimit).where(db.ConcurrencyLimit.tag == tag)

    result = await session.query(query)
    return result.scalar()


@inject_db
async def delete_concurrency_limit(
    session: sa.orm.Session,
    concurrency_limit_id: UUID,
    db: OrionDBInterface,
) -> bool:

    query = sa.delete(db.ConcurrencyLimit).where(
        db.ConcurrencyLimit.id == concurrency_limit_id
    )

    result = sa.execute(query)
    return result.rowcount > 0
