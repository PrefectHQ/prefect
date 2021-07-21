from typing import List
import sqlalchemy as sa
from sqlalchemy import select, delete

from prefect.orion.models import orm
from prefect.orion import schemas


async def create_flow_run(
    session: sa.orm.Session, flow_run: schemas.actions.FlowRunCreate
) -> orm.FlowRun:
    new_flow_run = orm.FlowRun(**flow_run.dict())
    session.add(new_flow_run)
    await session.flush()
    return new_flow_run


async def read_flow_run(session: sa.orm.Session, id: str) -> orm.FlowRun:
    return await session.get(orm.FlowRun, id)


async def read_flow_runs(
    session: sa.orm.Session,
    offset: int = 0,
    limit: int = 10,
) -> List[orm.FlowRun]:
    query = select(orm.FlowRun).offset(offset).limit(limit).order_by(orm.FlowRun.id)
    result = await session.execute(query)
    return result.scalars().all()


async def delete_flow_run(session: sa.orm.Session, id: str) -> bool:
    result = await session.execute(delete(orm.FlowRun).where(orm.FlowRun.id == id))
    return result.rowcount > 0
