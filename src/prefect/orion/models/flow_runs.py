from typing import Any, Dict, List
import sqlalchemy as sa
from sqlalchemy import select, delete

from prefect.orion.models import orm


async def create_flow_run(
    session: sa.orm.Session,
    flow_id: str,
    flow_version: str,
    parameters: Dict[str, Any] = None,
    parent_task_run_id: str = None,
    context: Dict[str, Any] = None,
    tags: List[str] = None,
) -> orm.FlowRun:
    flow_run = orm.FlowRun(
        flow_id=flow_id,
        flow_version=flow_version,
        parameters=parameters,
        parent_task_run_id=parent_task_run_id,
        context=context,
        tags=tags,
    )
    session.add(flow_run)
    await session.flush()
    return flow_run


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
