from typing import List
import sqlalchemy as sa
from fastapi import Depends, HTTPException, Body

from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/flow_run_states", tags=["Flow Run States"])


@router.post("/")
async def create_flow_run_state(
    flow_run_id: str = Body(...),
    state: schemas.actions.StateCreate = Body(...),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.FlowRunState:
    """
    Create a flow run state, disregarding orchestration logic
    """
    return await models.flow_run_states.create_flow_run_state(
        session=session, state=state, flow_run_id=flow_run_id
    )


@router.get("/{id}")
async def read_flow_run_state(
    id: str, session: sa.orm.Session = Depends(dependencies.get_session)
) -> schemas.core.FlowRunState:
    """
    Get a flow run state by id
    """
    flow_run_state = await models.flow_run_states.read_flow_run_state(
        session=session, id=id
    )
    if not flow_run_state:
        raise HTTPException(status_code=404, detail="Flow run state not found")
    return flow_run_state


@router.get("/")
async def read_flow_run_states(
    flow_run_id: str,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.FlowRunState]:
    """
    Get states associated with a flow run
    """
    return await models.flow_run_states.read_flow_run_states(
        session=session, flow_run_id=flow_run_id
    )
