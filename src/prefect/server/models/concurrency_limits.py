"""
Functions for interacting with concurrency limit ORM objects.
Intended for internal use by the Prefect REST API.
"""

from typing import List, Optional, Sequence, Union
from uuid import UUID

import pendulum
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.schemas as schemas
from prefect.server.database import orm_models
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface


@db_injector
async def create_concurrency_limit(
    db: PrefectDBInterface,
    session: AsyncSession,
    concurrency_limit: schemas.core.ConcurrencyLimit,
) -> orm_models.ConcurrencyLimit:
    insert_values = concurrency_limit.model_dump_for_orm(exclude_unset=False)
    insert_values.pop("created")
    insert_values.pop("updated")
    concurrency_tag = insert_values["tag"]

    # set `updated` manually
    # known limitation of `on_conflict_do_update`, will not use `Column.onupdate`
    # https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#the-set-clause
    concurrency_limit.updated = pendulum.now("UTC")  # type: ignore[assignment]

    insert_stmt = (
        db.insert(orm_models.ConcurrencyLimit)
        .values(**insert_values)
        .on_conflict_do_update(
            index_elements=db.concurrency_limit_unique_upsert_columns,
            set_=concurrency_limit.model_dump_for_orm(
                include={"concurrency_limit", "updated"}
            ),
        )
    )

    await session.execute(insert_stmt)

    query = (
        sa.select(orm_models.ConcurrencyLimit)
        .where(orm_models.ConcurrencyLimit.tag == concurrency_tag)
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    return result.scalar_one()


async def read_concurrency_limit(
    session: AsyncSession,
    concurrency_limit_id: UUID,
) -> Union[orm_models.ConcurrencyLimit, None]:
    """
    Reads a concurrency limit by id. If used for orchestration, simultaneous read race
    conditions might allow the concurrency limit to be temporarily exceeded.
    """

    query = sa.select(orm_models.ConcurrencyLimit).where(
        orm_models.ConcurrencyLimit.id == concurrency_limit_id
    )

    result = await session.execute(query)
    return result.scalar()


async def read_concurrency_limit_by_tag(
    session: AsyncSession,
    tag: str,
) -> Union[orm_models.ConcurrencyLimit, None]:
    """
    Reads a concurrency limit by tag. If used for orchestration, simultaneous read race
    conditions might allow the concurrency limit to be temporarily exceeded.
    """

    query = sa.select(orm_models.ConcurrencyLimit).where(
        orm_models.ConcurrencyLimit.tag == tag
    )

    result = await session.execute(query)
    return result.scalar()


async def reset_concurrency_limit_by_tag(
    session: AsyncSession,
    tag: str,
    slot_override: Optional[List[UUID]] = None,
) -> Union[orm_models.ConcurrencyLimit, None]:
    """
    Resets a concurrency limit by tag.
    """
    query = sa.select(orm_models.ConcurrencyLimit).where(
        orm_models.ConcurrencyLimit.tag == tag
    )
    result = await session.execute(query)
    concurrency_limit = result.scalar()
    if concurrency_limit:
        if slot_override is not None:
            concurrency_limit.active_slots = [str(slot) for slot in slot_override]
        else:
            concurrency_limit.active_slots = []
    return concurrency_limit


async def filter_concurrency_limits_for_orchestration(
    session: AsyncSession,
    tags: List[str],
) -> Sequence[orm_models.ConcurrencyLimit]:
    """
    Filters concurrency limits by tag. This will apply a "select for update" lock on
    these rows to prevent simultaneous read race conditions from enabling the
    the concurrency limit on these tags from being temporarily exceeded.
    """

    query = (
        sa.select(orm_models.ConcurrencyLimit)
        .filter(orm_models.ConcurrencyLimit.tag.in_(tags))
        .order_by(orm_models.ConcurrencyLimit.tag)
        .with_for_update()
    )
    result = await session.execute(query)
    return result.scalars().all()


async def delete_concurrency_limit(
    session: AsyncSession,
    concurrency_limit_id: UUID,
) -> bool:
    query = sa.delete(orm_models.ConcurrencyLimit).where(
        orm_models.ConcurrencyLimit.id == concurrency_limit_id
    )

    result = await session.execute(query)
    return result.rowcount > 0


async def delete_concurrency_limit_by_tag(
    session: AsyncSession,
    tag: str,
) -> bool:
    query = sa.delete(orm_models.ConcurrencyLimit).where(
        orm_models.ConcurrencyLimit.tag == tag
    )

    result = await session.execute(query)
    return result.rowcount > 0


async def read_concurrency_limits(
    session: AsyncSession,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> Sequence[orm_models.ConcurrencyLimit]:
    """
    Reads a concurrency limits. If used for orchestration, simultaneous read race
    conditions might allow the concurrency limit to be temporarily exceeded.

    Args:
        session: A database session
        offset: Query offset
        limit: Query limit

    Returns:
        List[orm_models.ConcurrencyLimit]: concurrency limits
    """

    query = sa.select(orm_models.ConcurrencyLimit).order_by(
        orm_models.ConcurrencyLimit.tag
    )

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()
