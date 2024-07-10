"""
Functions for interacting with saved search ORM objects.
Intended for internal use by the Prefect REST API.
"""

from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

import prefect.server.schemas as schemas
from prefect.server.database import orm_models
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface


@db_injector
async def create_saved_search(
    db: PrefectDBInterface,
    session: sa.orm.Session,
    saved_search: schemas.core.SavedSearch,
):
    """
    Upserts a SavedSearch.

    If a SavedSearch with the same name exists, all properties will be updated.

    Args:
        session (sa.orm.Session): a database session
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
    model = result.scalar()

    return model


async def read_saved_search(session: sa.orm.Session, saved_search_id: UUID):
    """
    Reads a SavedSearch by id.

    Args:
        session (sa.orm.Session): A database session
        saved_search_id (str): a SavedSearch id

    Returns:
        orm_models.SavedSearch: the SavedSearch
    """

    return await session.get(orm_models.SavedSearch, saved_search_id)


async def read_saved_search_by_name(session: sa.orm.Session, name: str):
    """
    Reads a SavedSearch by name.

    Args:
        session (sa.orm.Session): A database session
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
    session: sa.orm.Session,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
):
    """
    Read SavedSearches.

    Args:
        session (sa.orm.Session): A database session
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


async def delete_saved_search(session: sa.orm.Session, saved_search_id: UUID) -> bool:
    """
    Delete a SavedSearch by id.

    Args:
        session (sa.orm.Session): A database session
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
