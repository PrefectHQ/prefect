from typing import List

import sqlalchemy as sa
from fastapi import Depends, HTTPException

from prefect.orion import models
from prefect.orion.api import schemas
from prefect.orion.utilities.server import OrionRouter, get_session

router = OrionRouter(prefix="/flows", tags=["flows"])


@router.post("/")
async def create_flow(
    flow: schemas.Flow, session: sa.orm.Session = Depends(get_session)
) -> schemas.Flow:
    return await models.flows.create_flow(session=session, name=flow.name)


@router.get("/{flow_id}")
async def read_flow(
    flow_id: str, session: sa.orm.Session = Depends(get_session)
) -> schemas.Flow:
    flow = await models.flows.read_flow(session=session, id=flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


@router.get("/")
async def read_flows(
    offset: int = 0,
    limit: int = 10,
    session: sa.orm.Session = Depends(get_session),
) -> List[schemas.Flow]:
    return await models.flows.read_flows(session=session, offset=offset, limit=limit)


@router.delete("/{flow_id}", status_code=204)
async def delete_flow(flow_id: str, session: sa.orm.Session = Depends(get_session)):
    result = await models.flows.delete_flow(session=session, id=flow_id)
    if not result:
        raise HTTPException(status_code=404, detail="Flow not found")
    return result
