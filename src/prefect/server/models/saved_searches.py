"""
Functions for interacting with saved search ORM objects.
Intended for internal use by the Prefect REST API.
"""

from typing import Optional, Sequence, Union
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.schemas as schemas
from prefect.server.database import orm_models
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface


@db_injector
async def create_saved_search(
    db: PrefectDBInterface,
    session: AsyncSession,
    saved_search: schemas.core.SavedSearch,
) -> orm_models.SavedSearch:
    """
    Upserts a SavedSearch.

    If a SavedSearch with the same name exists, all properties will be updated.

    Args:
        session (AsyncSession): a database session
        saved_search (schemas.core.SavedSearch): a SavedSearch model

    Returns:
        orm_models.SavedSearch: the newly-created or updated SavedSearch
    """

    insert_stmt = (
        db.insert(orm_models.SavedSearch)
        .values(**saved_search.model_dump_for_orm(exclude_unset=True))
        .on_conflict_do_update(
            index_elements=db.saved_search_unique_upsert_columns,
            set_=saved_search.model_dump_for_orm(include={"filters"}),
        )
    )

    await session.execute(insert_stmt)

    query = (
        sa.select(orm_models.SavedSearch)
        .where(
            orm_models.SavedSearch.name == saved_search.name,
        )
        .execution_options(populate_existing=True)
    )
    result = await session.execute(query)
    model = result.scalar_one()

    return model


async def read_saved_search(
    session: AsyncSession, saved_search_id: UUID
) -> Union[orm_models.SavedSearch, None]:
    """
    Reads a SavedSearch by id.

    Args:
        session (AsyncSession): A database session
        saved_search_id (str): a SavedSearch id

    Returns:
        orm_models.SavedSearch: the SavedSearch
    """

    return await session.get(orm_models.SavedSearch, saved_search_id)


async def read_saved_search_by_name(
    session: AsyncSession, name: str
) -> Union[orm_models.SavedSearch, None]:
    """
    Reads a SavedSearch by name.

    Args:
        session (AsyncSession): A database session
        name (str): a SavedSearch name

    Returns:
        orm_models.SavedSearch: the SavedSearch
    """
    result = await session.execute(
        select(orm_models.SavedSearch)
        .where(orm_models.SavedSearch.name == name)
        .limit(1)
    )
    return result.scalar()


async def read_saved_searches(
    session: AsyncSession,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> Sequence[orm_models.SavedSearch]:
    """
    Read SavedSearches.

    Args:
        session (AsyncSession): A database session
        offset (int): Query offset
        limit(int): Query limit

    Returns:
        List[orm_models.SavedSearch]: SavedSearches
    """

    query = select(orm_models.SavedSearch).order_by(orm_models.SavedSearch.name)

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


async def delete_saved_search(session: AsyncSession, saved_search_id: UUID) -> bool:
    """
    Delete a SavedSearch by id.

    Args:
        session (AsyncSession): A database session
        saved_search_id (str): a SavedSearch id

    Returns:
        bool: whether or not the SavedSearch was deleted
    """

    result = await session.execute(
        delete(orm_models.SavedSearch).where(
            orm_models.SavedSearch.id == saved_search_id
        )
    )
    return result.rowcount > 0
