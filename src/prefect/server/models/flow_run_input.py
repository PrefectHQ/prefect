import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.schemas as schemas
from prefect.server.database.dependencies import inject_db
from prefect.server.database.interface import PrefectDBInterface


@inject_db
async def create_flow_run_input(
    session: AsyncSession,
    db: PrefectDBInterface,
    flow_run_input: schemas.core.FlowRunInput,
) -> schemas.core.FlowRunInput:
    model = db.FlowRunInput(**flow_run_input.dict())
    session.add(model)
    await session.flush()

    return schemas.core.FlowRunInput.from_orm(model)


@inject_db
async def read_flow_run_input(
    session: AsyncSession,
    db: PrefectDBInterface,
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
        return schemas.core.FlowRunInput.from_orm(model)

    return None


@inject_db
async def delete_flow_run_input(
    session: AsyncSession,
    db: PrefectDBInterface,
    flow_run_id: uuid.UUID,
    key: str,
) -> bool:
    result = await session.execute(
        sa.delete(db.FlowRunInput).where(
            sa.and_(
                db.FlowRunInput.flow_run_id == flow_run_id, db.FlowRunInput.key == key
            )
        )
    )

    return result.rowcount > 0
