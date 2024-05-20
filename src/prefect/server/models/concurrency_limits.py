"""
Functions for interacting with concurrency limit ORM objects.
Intended for internal use by the Prefect REST API.
"""

from typing import List, Optional
from uuid import UUID

import pendulum
import sqlalchemy as sa

import prefect.server.schemas as schemas
from prefect.server.database.dependencies import inject_db
from prefect.server.database.interface import PrefectDBInterface


@inject_db
async def create_concurrency_limit(
    session: sa.orm.Session,
    concurrency_limit: schemas.core.ConcurrencyLimit,
    db: PrefectDBInterface,
):
    insert_values = concurrency_limit.dict(shallow=True, exclude_unset=False)
    insert_values.pop("created")
    insert_values.pop("updated")
    concurrency_tag = insert_values["tag"]

    # set `updated` manually
    # known limitation of `on_conflict_do_update`, will not use `Column.onupdate`
    # https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#the-set-clause
    concurrency_limit.updated = pendulum.now("UTC")

    insert_stmt = (
        db.insert(db.ConcurrencyLimit)
        .values(**insert_values)
        .on_conflict_do_update(
            index_elements=db.concurrency_limit_unique_upsert_columns,
            set_=concurrency_limit.dict(
                shallow=True, include={"concurrency_limit", "updated"}
            ),
        )
    )

    await session.execute(insert_stmt)

    query = (
        sa.select(db.ConcurrencyLimit)
        .where(db.ConcurrencyLimit.tag == concurrency_tag)
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    return result.scalar()


@inject_db
async def read_concurrency_limit(
    session: sa.orm.Session,
    concurrency_limit_id: UUID,
    db: PrefectDBInterface,
):
    """
    Reads a concurrency limit by id. If used for orchestration, simultaneous read race
    conditions might allow the concurrency limit to be temporarily exceeded.
    """

    query = sa.select(db.ConcurrencyLimit).where(
        db.ConcurrencyLimit.id == concurrency_limit_id
    )

    result = await session.execute(query)
    return result.scalar()


@inject_db
async def read_concurrency_limit_by_tag(
    session: sa.orm.Session,
    tag: str,
    db: PrefectDBInterface,
):
    """
    Reads a concurrency limit by tag. If used for orchestration, simultaneous read race
    conditions might allow the concurrency limit to be temporarily exceeded.
    """

    query = sa.select(db.ConcurrencyLimit).where(db.ConcurrencyLimit.tag == tag)

    result = await session.execute(query)
    return result.scalar()


@inject_db
async def reset_concurrency_limit_by_tag(
    session: sa.orm.Session,
    tag: str,
    db: PrefectDBInterface,
    slot_override: Optional[List[UUID]] = None,
):
    """
    Resets a concurrency limit by tag.
    """
    query = sa.select(db.ConcurrencyLimit).where(db.ConcurrencyLimit.tag == tag)
    result = await session.execute(query)
    concurrency_limit = result.scalar()
    if concurrency_limit:
        if slot_override is not None:
            concurrency_limit.active_slots = [str(slot) for slot in slot_override]
        else:
            concurrency_limit.active_slots = []
    return concurrency_limit


@inject_db
async def filter_concurrency_limits_for_orchestration(
    session: sa.orm.Session,
    tags: List[str],
    db: PrefectDBInterface,
):
    """
    Filters concurrency limits by tag. This will apply a "select for update" lock on
    these rows to prevent simultaneous read race conditions from enabling the
    the concurrency limit on these tags from being temporarily exceeded.
    """

    query = (
        sa.select(db.ConcurrencyLimit)
        .filter(db.ConcurrencyLimit.tag.in_(tags))
        .order_by(db.ConcurrencyLimit.tag)
        .with_for_update()
    )
    result = await session.execute(query)
    return result.scalars().all()


@inject_db
async def delete_concurrency_limit(
    session: sa.orm.Session,
    concurrency_limit_id: UUID,
    db: PrefectDBInterface,
) -> bool:
    query = sa.delete(db.ConcurrencyLimit).where(
        db.ConcurrencyLimit.id == concurrency_limit_id
    )

    result = await session.execute(query)
    return result.rowcount > 0


@inject_db
async def delete_concurrency_limit_by_tag(
    session: sa.orm.Session,
    tag: str,
    db: PrefectDBInterface,
) -> bool:
    query = sa.delete(db.ConcurrencyLimit).where(db.ConcurrencyLimit.tag == tag)

    result = await session.execute(query)
    return result.rowcount > 0


@inject_db
async def read_concurrency_limits(
    session: sa.orm.Session,
    db: PrefectDBInterface,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
):
    """
    Reads a concurrency limits. If used for orchestration, simultaneous read race
    conditions might allow the concurrency limit to be temporarily exceeded.

    Args:
        session: A database session
        offset: Query offset
        limit: Query limit

    Returns:
        List[db.ConcurrencyLimit]: concurrency limits
    """

    query = sa.select(db.ConcurrencyLimit).order_by(db.ConcurrencyLimit.tag)

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()
