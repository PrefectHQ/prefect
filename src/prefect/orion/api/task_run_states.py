"""
Routes for interacting with task run state objects.
"""

from typing import List
from uuid import UUID

import sqlalchemy as sa
from fastapi import Depends, HTTPException, Path, status

import prefect.orion.api.dependencies as dependencies
import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/task_run_states", tags=["Task Run States"])


@router.get("/{id}")
async def read_task_run_state(
    task_run_state_id: UUID = Path(
        ..., description="The task run state id", alias="id"
    ),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> schemas.states.State:
    """
    Get a task run state by id.
    """
    task_run_state = await models.task_run_states.read_task_run_state(
        session=session, task_run_state_id=task_run_state_id
    )
    if not task_run_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flow run state not found"
        )
    return task_run_state


@router.get("/")
async def read_task_run_states(
    task_run_id: UUID,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.states.State]:
    """
    Get states associated with a task run.
    """
    return await models.task_run_states.read_task_run_states(
        session=session, task_run_id=task_run_id
    )
