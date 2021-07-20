from typing import List

import sqlalchemy as sa
from fastapi import Depends, HTTPException

from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/flow_runs", tags=["flow_runs"])


@router.post("/")
async def create_flow_run(
    flow_run: schemas.inputs.FlowRunCreate,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.api.FlowRun:
    return await models.flow_runs.create_flow_run(session=session, flow_run=flow_run)


@router.get("/{flow_run_id}")
async def read_flow_run(
    flow_run_id: str, session: sa.orm.Session = Depends(dependencies.get_session)
) -> schemas.api.FlowRun:
    flow_run = await models.flow_runs.read_flow_run(session=session, id=flow_run_id)
    if not flow_run:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow_run


@router.get("/")
async def read_flow_runs(
    offset: int = 0,
    limit: int = 10,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.api.FlowRun]:
    return await models.flow_runs.read_flow_runs(
        session=session, offset=offset, limit=limit
    )


@router.delete("/{flow_run_id}", status_code=204)
async def delete_flow_run(
    flow_run_id: str, session: sa.orm.Session = Depends(dependencies.get_session)
):
    result = await models.flow_runs.delete_flow_run(session=session, id=flow_run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Flow not found")
    return result
