"""
Routes for interacting with work queue objects.
"""
from typing import List, Optional
from uuid import UUID

import sqlalchemy as sa
from fastapi import Body, Depends, HTTPException, Path, status

import prefect.orion.api.dependencies as dependencies
import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.utilities.schemas import DateTimeTZ
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/work_queues", tags=["Work Queues"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_work_queue(
    work_queue: schemas.actions.WorkQueueCreate,
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.WorkQueue:
    """
    Creates a new work queue.

    If a work queue with the same name already exists, an error
    will be raised.
    """

    try:
        async with db.session_context(begin_transaction=True) as session:
            model = await models.work_queues.create_work_queue(
                session=session, work_queue=work_queue
            )
    except sa.exc.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A work queue with this name already exists.",
        )

    return model


@router.patch("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_work_queue(
    work_queue: schemas.actions.WorkQueueUpdate,
    work_queue_id: UUID = Path(..., description="The work queue id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    """
    Updates an existing work queue.
    """
    async with db.session_context(begin_transaction=True) as session:
        result = await models.work_queues.update_work_queue(
            session=session, work_queue_id=work_queue_id, work_queue=work_queue
        )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Work Queue {id} not found"
        )


@router.get("/name/{name}")
async def read_work_queue_by_name(
    name: str = Path(..., description="The work queue name"),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.WorkQueue:
    """
    Get a work queue by id.
    """
    async with db.session_context() as session:
        work_queue = await models.work_queues.read_work_queue_by_name(
            session=session, name=name
        )
    if not work_queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="work queue not found"
        )
    return work_queue


@router.get("/{id}")
async def read_work_queue(
    work_queue_id: UUID = Path(..., description="The work queue id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.WorkQueue:
    """
    Get a work queue by id.
    """
    async with db.session_context() as session:
        work_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue_id
        )
    if not work_queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="work queue not found"
        )
    return work_queue


@router.post("/{id}/get_runs")
async def read_work_queue_runs(
    work_queue_id: UUID = Path(..., description="The work queue id", alias="id"),
    limit: int = dependencies.LimitBody(),
    scheduled_before: DateTimeTZ = Body(
        None,
        description="Only flow runs scheduled to start before this time will be returned.",
    ),
    agent_id: Optional[UUID] = Body(
        None,
        description="An optional unique identifier for the agent making this query. If provided, the Orion API will track the last time this agent polled the work queue.",
    ),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.FlowRun]:
    """
    Get flow runs from the work queue.
    """
    async with db.session_context(begin_transaction=True) as session:
        flow_runs = await models.work_queues.get_runs_in_work_queue(
            session=session,
            work_queue_id=work_queue_id,
            scheduled_before=scheduled_before,
            limit=limit,
        )

        if agent_id:
            await models.agents.record_agent_poll(
                session=session, agent_id=agent_id, work_queue_id=work_queue_id
            )

    return flow_runs


@router.post("/filter")
async def read_work_queues(
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.WorkQueue]:
    """
    Query for work queues.
    """
    async with db.session_context() as session:
        return await models.work_queues.read_work_queues(
            session=session,
            offset=offset,
            limit=limit,
        )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_queue(
    work_queue_id: UUID = Path(..., description="The work queue id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    """
    Delete a work queue by id.
    """
    async with db.session_context(begin_transaction=True) as session:
        result = await models.work_queues.delete_work_queue(
            session=session, work_queue_id=work_queue_id
        )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="work queue not found"
        )
