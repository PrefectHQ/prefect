"""
Routes for interacting with work queue objects.
"""

from typing import List, Optional
from uuid import UUID

import sqlalchemy as sa
from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    Header,
    HTTPException,
    Path,
    status,
)

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.server.database import (
    PrefectDBInterface,
    provide_database_interface,
)
from prefect.server.models.deployments import mark_deployments_ready
from prefect.server.models.work_queues import (
    emit_work_queue_status_event,
    mark_work_queues_ready,
)
from prefect.server.schemas.statuses import WorkQueueStatus
from prefect.server.utilities.server import PrefectRouter
from prefect.types import DateTime

router: PrefectRouter = PrefectRouter(prefix="/work_queues", tags=["Work Queues"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_work_queue(
    work_queue: schemas.actions.WorkQueueCreate,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.responses.WorkQueueResponse:
    """
    Creates a new work queue.

    If a work queue with the same name already exists, an error
    will be raised.

    For more information, see https://docs.prefect.io/v3/deploy/infrastructure-concepts/work-pools#work-queues.
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

    return schemas.responses.WorkQueueResponse.model_validate(
        model, from_attributes=True
    )


@router.patch("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_work_queue(
    work_queue: schemas.actions.WorkQueueUpdate,
    work_queue_id: UUID = Path(..., description="The work queue id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """
    Updates an existing work queue.
    """
    async with db.session_context(begin_transaction=True) as session:
        result = await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=work_queue_id,
            work_queue=work_queue,
            emit_status_change=emit_work_queue_status_event,
        )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Work Queue {id} not found"
        )


@router.get("/name/{name}")
async def read_work_queue_by_name(
    name: str = Path(..., description="The work queue name"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.responses.WorkQueueResponse:
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
    return schemas.responses.WorkQueueResponse.model_validate(
        work_queue, from_attributes=True
    )


@router.get("/{id}")
async def read_work_queue(
    work_queue_id: UUID = Path(..., description="The work queue id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.responses.WorkQueueResponse:
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
    return schemas.responses.WorkQueueResponse.model_validate(
        work_queue, from_attributes=True
    )


@router.post("/{id}/get_runs")
async def read_work_queue_runs(
    background_tasks: BackgroundTasks,
    work_queue_id: UUID = Path(..., description="The work queue id", alias="id"),
    limit: int = dependencies.LimitBody(),
    scheduled_before: DateTime = Body(
        None,
        description=(
            "Only flow runs scheduled to start before this time will be returned."
        ),
    ),
    x_prefect_ui: Optional[bool] = Header(
        default=False,
        description="A header to indicate this request came from the Prefect UI.",
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.responses.FlowRunResponse]:
    """
    Get flow runs from the work queue.
    """
    async with db.session_context(begin_transaction=True) as session:
        work_queue, flow_runs = await models.work_queues.get_runs_in_work_queue(
            session=session,
            work_queue_id=work_queue_id,
            scheduled_before=scheduled_before,
            limit=limit,
        )

    # The Prefect UI often calls this route to see which runs are enqueued.
    # We do not want to record this as an actual poll event.
    if x_prefect_ui:
        return flow_runs

    background_tasks.add_task(
        mark_work_queues_ready,
        db=db,
        polled_work_queue_ids=[work_queue_id],
        ready_work_queue_ids=(
            [work_queue_id] if work_queue.status == WorkQueueStatus.NOT_READY else []
        ),
    )

    background_tasks.add_task(
        mark_deployments_ready,
        db=db,
        work_queue_ids=[work_queue_id],
    )

    return flow_runs


@router.post("/filter")
async def read_work_queues(
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    work_queues: schemas.filters.WorkQueueFilter = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.responses.WorkQueueResponse]:
    """
    Query for work queues.
    """
    async with db.session_context() as session:
        wqs = await models.work_queues.read_work_queues(
            session=session, offset=offset, limit=limit, work_queue_filter=work_queues
        )

    return [
        schemas.responses.WorkQueueResponse.model_validate(wq, from_attributes=True)
        for wq in wqs
    ]


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_queue(
    work_queue_id: UUID = Path(..., description="The work queue id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
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


@router.get("/{id}/status")
async def read_work_queue_status(
    work_queue_id: UUID = Path(..., description="The work queue id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.core.WorkQueueStatusDetail:
    """
    Get the status of a work queue.
    """
    async with db.session_context() as session:
        work_queue_status = await models.work_queues.read_work_queue_status(
            session=session, work_queue_id=work_queue_id
        )
    return work_queue_status
