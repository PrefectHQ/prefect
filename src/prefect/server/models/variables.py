from typing import Optional, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import orm_models
from prefect.server.schemas import filters, sorting
from prefect.server.schemas.actions import VariableCreate, VariableUpdate


async def create_variable(
    session: AsyncSession, variable: VariableCreate
) -> orm_models.Variable:
    """
    Create a variable

    Args:
        session: async database session
        variable: variable to create

    Returns:
        orm_models.Variable
    """
    model = orm_models.Variable(**variable.model_dump())
    session.add(model)
    await session.flush()

    return model


async def read_variable(
    session: AsyncSession, variable_id: UUID
) -> Optional[orm_models.Variable]:
    """
    Reads a variable by id.
    """

    query = sa.select(orm_models.Variable).where(orm_models.Variable.id == variable_id)

    result = await session.execute(query)
    return result.scalar()


async def read_variable_by_name(
    session: AsyncSession, name: str
) -> Optional[orm_models.Variable]:
    """
    Reads a variable by name.
    """

    query = sa.select(orm_models.Variable).where(orm_models.Variable.name == name)

    result = await session.execute(query)
    return result.scalar()


async def read_variables(
    session: AsyncSession,
    variable_filter: Optional[filters.VariableFilter] = None,
    sort: sorting.VariableSort = sorting.VariableSort.NAME_ASC,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> Sequence[orm_models.Variable]:
    """
    Read variables, applying filers.
    """
    query = sa.select(orm_models.Variable).order_by(sort.as_sql_sort())

    if variable_filter:
        query = query.where(variable_filter.as_sql_filter())

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


async def count_variables(
    session: AsyncSession, variable_filter: Optional[filters.VariableFilter] = None
) -> int:
    """
    Count variables, applying filters.
    """

    query = sa.select(sa.func.count()).select_from(orm_models.Variable)

    if variable_filter:
        query = query.where(variable_filter.as_sql_filter())

    result = await session.execute(query)
    return result.scalar_one()


async def update_variable(
    session: AsyncSession, variable_id: UUID, variable: VariableUpdate
) -> bool:
    """
    Updates a variable by id.
    """
    query = (
        sa.update(orm_models.Variable)
        .where(orm_models.Variable.id == variable_id)
        .values(**variable.model_dump_for_orm(exclude_unset=True))
    )

    result = await session.execute(query)
    return result.rowcount > 0


async def update_variable_by_name(
    session: AsyncSession, name: str, variable: VariableUpdate
) -> bool:
    """
    Updates a variable by name.
    """
    query = (
        sa.update(orm_models.Variable)
        .where(orm_models.Variable.name == name)
        .values(**variable.model_dump_for_orm(exclude_unset=True))
    )

    result = await session.execute(query)
    return result.rowcount > 0


async def delete_variable(session: AsyncSession, variable_id: UUID) -> bool:
    """
    Delete a variable by id.
    """

    query = sa.delete(orm_models.Variable).where(orm_models.Variable.id == variable_id)

    result = await session.execute(query)
    return result.rowcount > 0


async def delete_variable_by_name(session: AsyncSession, name: str) -> bool:
    """
    Delete a variable by name.
    """

    query = sa.delete(orm_models.Variable).where(orm_models.Variable.name == name)

    result = await session.execute(query)
    return result.rowcount > 0
