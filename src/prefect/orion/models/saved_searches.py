"""
Functions for interacting with saved search ORM objects.
Intended for internal use by the Orion API.
"""

from typing import List
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.orion import schemas
from prefect.orion.models import orm
from prefect.orion.utilities.database import dialect_specific_insert


async def create_saved_search(
    session: sa.orm.Session,
    saved_search: schemas.core.SavedSearch,
) -> orm.SavedSearch:
    """
    Upserts a SavedSearch.

    If a SavedSearch with the same name exists, all properties will be updated.

    Args:
        session (sa.orm.Session): a database session
        saved_search (schemas.core.SavedSearch): a SavedSearch model

    Returns:
        orm.SavedSearch: the newly-created or updated SavedSearch

    """

    insert_stmt = (
        dialect_specific_insert(orm.SavedSearch)
        .values(**saved_search.dict(shallow=True, exclude_unset=True))
        .on_conflict_do_update(
            index_elements=["name"],
            set_=saved_search.dict(shallow=True, include={"filters"}),
        )
    )

    await session.execute(insert_stmt)

    query = (
        sa.select(orm.SavedSearch)
        .where(
            orm.SavedSearch.name == saved_search.name,
        )
        .execution_options(populate_existing=True)
    )
    result = await session.execute(query)
    model = result.scalar()

    return model


async def read_saved_search(
    session: sa.orm.Session, saved_search_id: UUID
) -> orm.SavedSearch:
    """
    Reads a SavedSearch by id.

    Args:
        session (sa.orm.Session): A database session
        saved_search_id (str): a SavedSearch id

    Returns:
        orm.SavedSearch: the SavedSearch
    """

    return await session.get(orm.SavedSearch, saved_search_id)


async def read_saved_search_by_name(
    session: sa.orm.Session,
    name: str,
) -> orm.SavedSearch:
    """
    Reads a SavedSearch by name.

    Args:
        session (sa.orm.Session): A database session
        name (str): a SavedSearch name

    Returns:
        orm.SavedSearch: the SavedSearch
    """
    result = await session.execute(
        select(orm.SavedSearch).where(orm.SavedSearch.name == name).limit(1)
    )
    return result.scalar()


async def read_saved_searches(
    session: sa.orm.Session,
    offset: int = None,
    limit: int = None,
) -> List[orm.SavedSearch]:
    """
    Read SavedSearchs.

    Args:
        session (sa.orm.Session): A database session
        offset (int): Query offset
        limit(int): Query limit

    Returns:
        List[orm.SavedSearch]: SavedSearchs
    """

    query = select(orm.SavedSearch).order_by(orm.SavedSearch.name)

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
        delete(orm.SavedSearch).where(orm.SavedSearch.id == saved_search_id)
    )
    return result.rowcount > 0
