from typing import List
import sqlalchemy as sa
from sqlalchemy import select, delete

from prefect.orion.models import orm
from prefect.orion import schemas


async def create_task_run(
    session: sa.orm.Session, task_run: schemas.actions.TaskRunCreate
) -> orm.TaskRun:
    new_task_run = orm.TaskRun(**task_run.dict())
    session.add(new_task_run)
    await session.flush()
    return new_task_run


async def read_task_run(session: sa.orm.Session, id: str) -> orm.TaskRun:
    return await session.get(orm.TaskRun, id)


async def read_task_runs(
    session: sa.orm.Session, flow_run_id: str
) -> List[orm.TaskRun]:
    query = (
        select(orm.TaskRun)
        .filter(orm.TaskRun.flow_run_id == flow_run_id)
        .order_by(orm.TaskRun.task_key)
    )
    result = await session.execute(query)
    return result.scalars().all()


async def delete_task_run(session: sa.orm.Session, id: str) -> bool:
    result = await session.execute(delete(orm.TaskRun).where(orm.TaskRun.id == id))
    return result.rowcount > 0
