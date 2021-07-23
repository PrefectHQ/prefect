from typing import List

import sqlalchemy as sa
from fastapi import Depends, HTTPException, Body

from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/flow_runs", tags=["Flow Runs"])


@router.post("/")
async def create_flow_run(
    flow_run: schemas.actions.FlowRunCreate,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.FlowRun:
    """
    Create a flow run
    """
    return await models.flow_runs.create_flow_run(session=session, flow_run=flow_run)


@router.get("/{flow_run_id}")
async def read_flow_run(
    flow_run_id: str, session: sa.orm.Session = Depends(dependencies.get_session)
) -> schemas.core.FlowRun:
    """
    Get a flow run by id
    """
    flow_run = await models.flow_runs.read_flow_run(session=session, id=flow_run_id)
    if not flow_run:
        raise HTTPException(status_code=404, detail="Flow run not found")
    return flow_run


@router.get("/")
async def read_flow_runs(
    offset: int = 0,
    limit: int = 10,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.FlowRun]:
    """
    Query for flow runs
    """
    return await models.flow_runs.read_flow_runs(
        session=session, offset=offset, limit=limit
    )


@router.delete("/{flow_run_id}", status_code=204)
async def delete_flow_run(
    flow_run_id: str, session: sa.orm.Session = Depends(dependencies.get_session)
):
    """
    Delete a flow run by id
    """
    result = await models.flow_runs.delete_flow_run(session=session, id=flow_run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Flow run not found")
    return result


@router.post("/{id}/set_state")
async def set_flow_run_state(
    id: str,
    state: schemas.actions.StateCreate = Body(..., description="The intended state."),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.responses.SetStateResponse:
    """Set a flow run state, invoking any orchestration rules."""

    # create the state
    await models.flow_run_states.create_flow_run_state(
        session=session, flow_run_id=id, state=state
    )

    # indicate the state was accepted
    return schemas.responses.SetStateResponse(
        status=schemas.responses.SetStateStatus.ACCEPT,
        state=None,
    )
