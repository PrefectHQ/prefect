import copy
import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.schemas as schemas
from prefect.server.database.dependencies import inject_db
from prefect.server.database.interface import PrefectDBInterface

# As of 2023-12-06 we're only planning on storing a single value per
# FlowRunInput, however we're storing the value as a list of items to
# allow for future expansion.
VALUE_CONTAINER = {"__prefect_metadata": {}, "items": []}


@inject_db
async def create_flow_run_input(
    session: AsyncSession,
    db: PrefectDBInterface,
    flow_run_input: schemas.actions.FlowRunInputCreate,
) -> schemas.core.FlowRunInput:
    data = flow_run_input.dict()

    container = copy.deepcopy(VALUE_CONTAINER)
    container["items"].append(
        {
            "_item_id": str(uuid.uuid4()),
            "value": data["value"],
        }
    )
    data["value"] = container

    model = db.FlowRunInput(**data)
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
async def update_flow_run_input(
    session: AsyncSession,
    db: PrefectDBInterface,
    flow_run_input: schemas.actions.FlowRunInputUpdate,
) -> bool:
    def set_value(new_value: str):
        if db.dialect.name == "sqlite":
            return sa.func.json_set(
                db.FlowRunInput.value, "$.items[0].value", new_value
            )
        else:
            return sa.func.jsonb_set(
                db.FlowRunInput.value,
                sa.text("'{items,0,value}'"),
                sa.cast(new_value, JSONB),
                True,
            )

    flow_run_id = flow_run_input.flow_run_id
    key = flow_run_input.key
    value = flow_run_input.value

    query = (
        sa.update(db.FlowRunInput)
        .where(
            sa.and_(
                db.FlowRunInput.flow_run_id == flow_run_id,
                db.FlowRunInput.key == key,
            )
        )
        .values(value=set_value(value))
    )

    result = await session.execute(query)
    return result.rowcount > 0


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
