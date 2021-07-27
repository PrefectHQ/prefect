from typing import List
import sqlalchemy as sa
from fastapi import Depends, HTTPException, Body, Path

from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/task_run_states", tags=["Task Run States"])


@router.post("/")
async def create_task_run_state(
    task_run_id: str = Body(...),
    state: schemas.actions.StateCreate = Body(...),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.State:
    """
    Create a task run state, disregarding orchestration logic
    """
    return await models.task_run_states.create_task_run_state(
        session=session, state=state, task_run_id=task_run_id
    )


@router.get("/{id}")
async def read_task_run_state(
    task_run_state_id: str = Path(..., description="The task run state id", alias="id"),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.core.State:
    """
    Get a task run state by id
    """
    task_run_state = await models.task_run_states.read_task_run_state(
        session=session, task_run_state_id=task_run_state_id
    )
    if not task_run_state:
        raise HTTPException(status_code=404, detail="Flow run state not found")
    return task_run_state


@router.get("/")
async def read_task_run_states(
    task_run_id: str,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.core.State]:
    """
    Get states associated with a task run
    """
    return await models.task_run_states.read_task_run_states(
        session=session, task_run_id=task_run_id
    )
