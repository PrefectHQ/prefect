from typing import Optional, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface, db_injector, orm_models
from prefect.server.events import clients
from prefect.server.events.schemas import lifecycle
from prefect.server.schemas import filters, sorting
from prefect.server.schemas.actions import VariableCreate, VariableUpdate
from prefect.types._datetime import now


async def emit_variable_created_event(variable: orm_models.Variable) -> None:
    """Emit an event when a variable is created."""
    async with clients.PrefectServerEventsClient() as events_client:
        await events_client.emit(lifecycle.variable_created_event(variable, now("UTC")))


async def emit_variable_updated_event(variable: orm_models.Variable) -> None:
    """Emit an event when a variable is updated."""
    async with clients.PrefectServerEventsClient() as events_client:
        await events_client.emit(lifecycle.variable_updated_event(variable, now("UTC")))


async def emit_variable_deleted_event(variable: orm_models.Variable) -> None:
    """Emit an event when a variable is deleted."""
    async with clients.PrefectServerEventsClient() as events_client:
        await events_client.emit(lifecycle.variable_deleted_event(variable, now("UTC")))


@db_injector
async def create_variable(
    db: PrefectDBInterface, session: AsyncSession, variable: VariableCreate
) -> orm_models.Variable:
    """
    Create a variable

    Args:
        session: async database session
        variable: variable to create

    Returns:
        orm_models.Variable
    """
    model = db.Variable(**variable.model_dump())
    session.add(model)
    await session.flush()

    await emit_variable_created_event(model)

    return model


@db_injector
async def read_variable(
    db: PrefectDBInterface, session: AsyncSession, variable_id: UUID
) -> Optional[orm_models.Variable]:
    """
    Reads a variable by id.
    """

    query = sa.select(db.Variable).where(db.Variable.id == variable_id)

    result = await session.execute(query)
    return result.scalar()


@db_injector
async def read_variable_by_name(
    db: PrefectDBInterface, session: AsyncSession, name: str
) -> Optional[orm_models.Variable]:
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
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> Sequence[orm_models.Variable]:
    """
    Read variables, applying filers.
    """
    query = sa.select(db.Variable).order_by(*sort.as_sql_sort())

    if variable_filter:
        query = query.where(variable_filter.as_sql_filter())

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
        query = query.where(variable_filter.as_sql_filter())

    result = await session.execute(query)
    return result.scalar_one()


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
    existing = await read_variable(session, variable_id)
    if existing is None:
        return False

    query = (
        sa.update(db.Variable)
        .where(db.Variable.id == variable_id)
        .values(**variable.model_dump_for_orm(exclude_unset=True))
    )
    await session.execute(query)

    await session.refresh(existing)
    await emit_variable_updated_event(existing)
    return True


@db_injector
async def update_variable_by_name(
    db: PrefectDBInterface, session: AsyncSession, name: str, variable: VariableUpdate
) -> bool:
    """
    Updates a variable by name.
    """
    existing = await read_variable_by_name(session, name)
    if existing is None:
        return False

    query = (
        sa.update(db.Variable)
        .where(db.Variable.id == existing.id)
        .values(**variable.model_dump_for_orm(exclude_unset=True))
    )
    await session.execute(query)

    await session.refresh(existing)
    await emit_variable_updated_event(existing)
    return True


@db_injector
async def delete_variable(
    db: PrefectDBInterface, session: AsyncSession, variable_id: UUID
) -> bool:
    """
    Delete a variable by id.
    """
    existing = await read_variable(session, variable_id)
    if existing is None:
        return False

    await emit_variable_deleted_event(existing)

    query = sa.delete(db.Variable).where(db.Variable.id == variable_id)
    await session.execute(query)
    return True


@db_injector
async def delete_variable_by_name(
    db: PrefectDBInterface, session: AsyncSession, name: str
) -> bool:
    """
    Delete a variable by name.
    """
    existing = await read_variable_by_name(session, name)
    if existing is None:
        return False

    await emit_variable_deleted_event(existing)

    query = sa.delete(db.Variable).where(db.Variable.id == existing.id)
    await session.execute(query)
    return True
