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
from prefect.server.database import PrefectDBInterface, db_injector, orm_models


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
        db.queries.insert(db.SavedSearch)
        .values(**saved_search.model_dump_for_orm(exclude_unset=True))
        .on_conflict_do_update(
            index_elements=db.orm.saved_search_unique_upsert_columns,
            set_=saved_search.model_dump_for_orm(include={"filters"}),
        )
    )

    await session.execute(insert_stmt)

    query = (
        sa.select(db.SavedSearch)
        .where(
            db.SavedSearch.name == saved_search.name,
        )
        .execution_options(populate_existing=True)
    )
    result = await session.execute(query)
    model = result.scalar_one()

    return model


@db_injector
async def read_saved_search(
    db: PrefectDBInterface, session: AsyncSession, saved_search_id: UUID
) -> Union[orm_models.SavedSearch, None]:
    """
    Reads a SavedSearch by id.

    Args:
        session (AsyncSession): A database session
        saved_search_id (str): a SavedSearch id

    Returns:
        orm_models.SavedSearch: the SavedSearch
    """

    return await session.get(db.SavedSearch, saved_search_id)


@db_injector
async def read_saved_search_by_name(
    db: PrefectDBInterface, session: AsyncSession, name: str
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
        select(db.SavedSearch).where(db.SavedSearch.name == name).limit(1)
    )
    return result.scalar()


@db_injector
async def read_saved_searches(
    db: PrefectDBInterface,
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

    query = select(db.SavedSearch).order_by(db.SavedSearch.name)

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@db_injector
async def delete_saved_search(
    db: PrefectDBInterface, session: AsyncSession, saved_search_id: UUID
) -> bool:
    """
    Delete a SavedSearch by id.

    Args:
        session (AsyncSession): A database session
        saved_search_id (str): a SavedSearch id

    Returns:
        bool: whether or not the SavedSearch was deleted
    """

    result = await session.execute(
        delete(db.SavedSearch).where(db.SavedSearch.id == saved_search_id)
    )
    return result.rowcount > 0
