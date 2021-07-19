from typing import List

import sqlalchemy as sa
from fastapi import Depends, HTTPException

from prefect.orion import models
from prefect.orion.api import schemas
from prefect.orion.utilities.server import OrionRouter, get_session

router = OrionRouter(prefix="/flow_runs", tags=["flow_runs"])


@router.post("/")
async def create_flow_run(
    flow_run: schemas.FlowRun, session: sa.orm.Session = Depends(get_session)
) -> schemas.FlowRun:
    return await models.flow_runs.create_flow_run(
        session=session,
        flow_id=flow_run.flow_id,
        flow_version=flow_run.flow_version,
        parameters=flow_run.parameters,
        parent_task_run_id=flow_run.parent_task_run_id,
        context=flow_run.context,
        tags=flow_run.tags,
    )


@router.get("/{flow_run_id}")
async def read_flow(
    flow_run_id: str, session: sa.orm.Session = Depends(get_session)
) -> schemas.FlowRun:
    flow_run = await models.flow_runs.read_flow_run(session=session, id=flow_run_id)
    if not flow_run:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow_run


@router.get("/")
async def read_flows(
    offset: int = 0,
    limit: int = 10,
    session: sa.orm.Session = Depends(get_session),
) -> List[schemas.FlowRun]:
    return await models.flow_runs.read_flow_runs(
        session=session, offset=offset, limit=limit
    )


@router.delete("/{flow_run_id}", status_code=204)
async def delete_flow(flow_run_id: str, session: sa.orm.Session = Depends(get_session)):
    result = await models.flow_runs.delete_flow_run(session=session, id=flow_run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Flow not found")
    return result
