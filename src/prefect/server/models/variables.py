from typing import TYPE_CHECKING, Optional, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.schemas import filters, sorting
from prefect.server.schemas.actions import VariableCreate, VariableUpdate

if TYPE_CHECKING:
    from prefect.server.database.orm_models import ORMVariable


@db_injector
async def create_variable(
    db: PrefectDBInterface,
    session: AsyncSession,
    variable: VariableCreate,
) -> "ORMVariable":
    """
    Create a variable

    Args:
        session: async database session
        variable: variable to create

    Returns:
        db.Variable
    """
    model = db.Variable(**variable.dict())
    session.add(model)
    await session.flush()

    return model


@db_injector
async def read_variable(
    db: PrefectDBInterface,
    session: AsyncSession,
    variable_id: UUID,
) -> Optional["ORMVariable"]:
    """
    Reads a variable by id.
    """

    query = sa.select(db.Variable).where(db.Variable.id == variable_id)

    result = await session.execute(query)
    return result.scalar()


@db_injector
async def read_variable_by_name(
    db: PrefectDBInterface,
    session: AsyncSession,
    name: str,
) -> Optional["ORMVariable"]:
    """
    Reads a variable by name.
    """

    query = sa.select(db.Variable).where(db.Variable.name == name)

    result = await session.execute(query)
    return result.scalar()


@db_injector
async def read_variables(
    db: PrefectDBInterface,
    session: AsyncSession,
    variable_filter: Optional[filters.VariableFilter] = None,
    sort: sorting.VariableSort = sorting.VariableSort.NAME_ASC,
    offset: int = None,
    limit: int = None,
) -> Sequence["ORMVariable"]:
    """
    Read variables, applying filers.
    """
    query = sa.select(db.Variable).order_by(sort.as_sql_sort(db))

    if variable_filter:
        query = query.where(variable_filter.as_sql_filter(db))

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@db_injector
async def count_variables(
    db: PrefectDBInterface,
    session: AsyncSession,
    variable_filter: Optional[filters.VariableFilter] = None,
) -> int:
    """
    Count variables, applying filters.
    """

    query = sa.select(sa.func.count()).select_from(db.Variable)

    if variable_filter:
        query = query.where(variable_filter.as_sql_filter(db))

    result = await session.execute(query)
    return result.scalar()


@db_injector
async def update_variable(
    db: PrefectDBInterface,
    session: AsyncSession,
    variable_id: UUID,
    variable: VariableUpdate,
) -> bool:
    """
    Updates a variable by id.
    """
    query = (
        sa.update(db.Variable)
        .where(db.Variable.id == variable_id)
        .values(**variable.dict(shallow=True, exclude_unset=True))
    )

    result = await session.execute(query)
    return result.rowcount > 0


@db_injector
async def update_variable_by_name(
    db: PrefectDBInterface,
    session: AsyncSession,
    name: str,
    variable: VariableUpdate,
) -> bool:
    """
    Updates a variable by name.
    """
    query = (
        sa.update(db.Variable)
        .where(db.Variable.name == name)
        .values(**variable.dict(shallow=True, exclude_unset=True))
    )

    result = await session.execute(query)
    return result.rowcount > 0


@db_injector
async def delete_variable(
    db: PrefectDBInterface,
    session: AsyncSession,
    variable_id: UUID,
) -> bool:
    """
    Delete a variable by id.
    """

    query = sa.delete(db.Variable).where(db.Variable.id == variable_id)

    result = await session.execute(query)
    return result.rowcount > 0


@db_injector
async def delete_variable_by_name(
    db: PrefectDBInterface,
    session: AsyncSession,
    name: str,
) -> bool:
    """
    Delete a variable by name.
    """

    query = sa.delete(db.Variable).where(db.Variable.name == name)

    result = await session.execute(query)
    return result.rowcount > 0
