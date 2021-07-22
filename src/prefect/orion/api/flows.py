from typing import List

import sqlalchemy as sa
from fastapi import Depends, HTTPException, Response, status

from prefect.orion import schemas, models
from prefect.orion.api import dependencies
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/flows", tags=["Flows"])


@router.post("/")
async def create_flow(
    flow: schemas.actions.FlowCreate,
    response: Response,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.Flow:
    """Gracefully creates a new flow from the provided schema. If a flow with the
    same name already exists, the existing flow is returned.
    """
    nested = await session.begin_nested()
    try:
        flow = await models.flows.create_flow(session=session, flow=flow)
        response.status_code = status.HTTP_201_CREATED
    except:
        await nested.rollback()
        flow = await models.flows.read_flow_by_name(session=session, name=flow.name)
    return flow


@router.get("/{flow_id}")
async def read_flow(
    flow_id: str, session: sa.orm.Session = Depends(dependencies.get_session)
) -> schemas.core.Flow:
    """
    Get a flow by id
    """
    flow = await models.flows.read_flow(session=session, id=flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


@router.get("/")
async def read_flows(
    pagination: dependencies.Pagination = Depends(),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.Flow]:
    """
    Query for flows
    """
    return await models.flows.read_flows(
        session=session, offset=pagination.offset, limit=pagination.limit
    )


@router.delete("/{flow_id}", status_code=204)
async def delete_flow(
    flow_id: str, session: sa.orm.Session = Depends(dependencies.get_session)
):
    """
    Delete a flow by id
    """
    result = await models.flows.delete_flow(session=session, id=flow_id)
    if not result:
        raise HTTPException(status_code=404, detail="Flow not found")
    return result
