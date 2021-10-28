"""
Functions for interacting with saved search ORM objects.
Intended for internal use by the Orion API.
"""

from typing import List
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db_config


@inject_db_config
async def create_saved_search(
    session: sa.orm.Session,
    saved_search: schemas.core.SavedSearch,
    db_config=None,
):
    """
    Upserts a SavedSearch.

    If a SavedSearch with the same name exists, all properties will be updated.

    Args:
        session (sa.orm.Session): a database session
        saved_search (schemas.core.SavedSearch): a SavedSearch model

    Returns:
        db_config.SavedSearch: the newly-created or updated SavedSearch

    """

    insert_stmt = (
        (await db_config.dialect_specific_insert(db_config.SavedSearch))
        .values(**saved_search.dict(shallow=True, exclude_unset=True))
        .on_conflict_do_update(
            index_elements=db_config.saved_search_unique_upsert_columns,
            set_=saved_search.dict(shallow=True, include={"filters"}),
        )
    )

    await session.execute(insert_stmt)

    query = (
        sa.select(db_config.SavedSearch)
        .where(
            db_config.SavedSearch.name == saved_search.name,
        )
        .execution_options(populate_existing=True)
    )
    result = await session.execute(query)
    model = result.scalar()

    return model


@inject_db_config
async def read_saved_search(
    session: sa.orm.Session,
    saved_search_id: UUID,
    db_config=None,
):
    """
    Reads a SavedSearch by id.

    Args:
        session (sa.orm.Session): A database session
        saved_search_id (str): a SavedSearch id

    Returns:
        db_config.SavedSearch: the SavedSearch
    """

    return await session.get(db_config.SavedSearch, saved_search_id)


@inject_db_config
async def read_saved_search_by_name(
    session: sa.orm.Session,
    name: str,
    db_config=None,
):
    """
    Reads a SavedSearch by name.

    Args:
        session (sa.orm.Session): A database session
        name (str): a SavedSearch name

    Returns:
        db_config.SavedSearch: the SavedSearch
    """
    result = await session.execute(
        select(db_config.SavedSearch).where(db_config.SavedSearch.name == name).limit(1)
    )
    return result.scalar()


@inject_db_config
async def read_saved_searches(
    session: sa.orm.Session,
    offset: int = None,
    limit: int = None,
    db_config=None,
):
    """
    Read SavedSearchs.

    Args:
        session (sa.orm.Session): A database session
        offset (int): Query offset
        limit(int): Query limit

    Returns:
        List[db_config.SavedSearch]: SavedSearchs
    """

    query = select(db_config.SavedSearch).order_by(db_config.SavedSearch.name)

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db_config
async def delete_saved_search(
    session: sa.orm.Session, saved_search_id: UUID, db_config=None
) -> bool:
    """
    Delete a SavedSearch by id.

    Args:
        session (sa.orm.Session): A database session
        saved_search_id (str): a SavedSearch id

    Returns:
        bool: whether or not the SavedSearch was deleted
    """

    result = await session.execute(
        delete(db_config.SavedSearch).where(db_config.SavedSearch.id == saved_search_id)
    )
    return result.rowcount > 0
