import uuid
from typing import List, Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.schemas as schemas
from prefect.server.database import PrefectDBInterface, db_injector


@db_injector
async def create_flow_run_input(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run_input: schemas.core.FlowRunInput,
) -> schemas.core.FlowRunInput:
    model = db.FlowRunInput(**flow_run_input.model_dump())
    session.add(model)
    await session.flush()

    return schemas.core.FlowRunInput.model_validate(model, from_attributes=True)


@db_injector
async def filter_flow_run_input(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run_id: uuid.UUID,
    prefix: str,
    limit: int,
    exclude_keys: List[str],
) -> List[schemas.core.FlowRunInput]:
    query = (
        sa.select(db.FlowRunInput)
        .where(
            sa.and_(
                db.FlowRunInput.flow_run_id == flow_run_id,
                db.FlowRunInput.key.like(prefix + "%"),
                db.FlowRunInput.key.not_in(exclude_keys),
            )
        )
        .order_by(db.FlowRunInput.created)
        .limit(limit)
    )

    result = await session.execute(query)
    return [
        schemas.core.FlowRunInput.model_validate(model, from_attributes=True)
        for model in result.scalars().all()
    ]


@db_injector
async def read_flow_run_input(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run_id: uuid.UUID,
    key: str,
) -> Optional[schemas.core.FlowRunInput]:
    query = sa.select(db.FlowRunInput).where(
        sa.and_(
            db.FlowRunInput.flow_run_id == flow_run_id,
            db.FlowRunInput.key == key,
        )
    )

    result = await session.execute(query)
    model = result.scalar()
    if model:
        return schemas.core.FlowRunInput.model_validate(model, from_attributes=True)

    return None


@db_injector
async def delete_flow_run_input(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run_id: uuid.UUID,
    key: str,
) -> bool:
    result = await session.execute(
        sa.delete(db.FlowRunInput).where(
            sa.and_(
                db.FlowRunInput.flow_run_id == flow_run_id,
                db.FlowRunInput.key == key,
            )
        )
    )

    return result.rowcount > 0
