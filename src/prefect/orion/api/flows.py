from typing import List
from fastapi import Depends, HTTPException, Query
import sqlalchemy as sa
from prefect.orion.api import schemas, app
from prefect.orion.utilities.server import get_session
from prefect.orion import models


@app.post("/flows/", response_model=schemas.Flow, status_code=201)
async def create_flow(
    flow: schemas.Flow, session: sa.orm.Session = Depends(get_session)
):
    return await models.flows.create_flow(session=session, name=flow.name)


@app.get("/flows/{flow_id}", response_model=schemas.Flow)
async def read_flow(flow_id: str, session: sa.orm.Session = Depends(get_session)):
    flow = await models.flows.read_flow(session=session, id=flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


@app.get("/flows/", response_model=List[schemas.Flow])
async def read_flows(
    offset: int = 0,
    limit: int = 10,
    order_by: List[str] = Query(None),
    session: sa.orm.Session = Depends(get_session),
):
    return await models.flows.read_flows(
        session=session, offset=offset, limit=limit, order_by=order_by
    )


@app.delete("/flows/{flow_id}", status_code=204)
async def delete_flow(flow_id: str, session: sa.orm.Session = Depends(get_session)):
    result = await models.flows.delete_flow(session=session, id=flow_id)
    if not result:
        raise HTTPException(status_code=404, detail="Flow not found")
    return result
