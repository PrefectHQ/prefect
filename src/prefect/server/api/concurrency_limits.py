"""
Routes for interacting with concurrency limit objects.
"""

from typing import List, Optional, Sequence
from uuid import UUID

from fastapi import Body, Depends, HTTPException, Path, Response, status

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.server.api.concurrency_limits_v2 import MinimalConcurrencyLimitResponse
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.models import concurrency_limits
from prefect.server.utilities.server import PrefectRouter
from prefect.settings import PREFECT_TASK_RUN_TAG_CONCURRENCY_SLOT_WAIT_SECONDS
from prefect.types._datetime import now

router: PrefectRouter = PrefectRouter(
    prefix="/concurrency_limits", tags=["Concurrency Limits"]
)


@router.post("/")
async def create_concurrency_limit(
    concurrency_limit: schemas.actions.ConcurrencyLimitCreate,
    response: Response,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.core.ConcurrencyLimit:
    """
    Create a task run concurrency limit.

    For more information, see https://docs.prefect.io/v3/develop/task-run-limits.
    """
    # hydrate the input model into a full model
    concurrency_limit_model = schemas.core.ConcurrencyLimit(
        **concurrency_limit.model_dump()
    )

    async with db.session_context(begin_transaction=True) as session:
        model = await models.concurrency_limits.create_concurrency_limit(
            session=session, concurrency_limit=concurrency_limit_model
        )

    if model.created >= now("UTC"):
        response.status_code = status.HTTP_201_CREATED

    return model


@router.get("/{id:uuid}")
async def read_concurrency_limit(
    concurrency_limit_id: UUID = Path(
        ..., description="The concurrency limit id", alias="id"
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.core.ConcurrencyLimit:
    """
    Get a concurrency limit by id.

    The `active slots` field contains a list of TaskRun IDs currently using a
    concurrency slot for the specified tag.
    """
    async with db.session_context() as session:
        model = await models.concurrency_limits.read_concurrency_limit(
            session=session, concurrency_limit_id=concurrency_limit_id
        )
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Concurrency limit not found"
        )
    return model


@router.get("/tag/{tag}")
async def read_concurrency_limit_by_tag(
    tag: str = Path(..., description="The tag name", alias="tag"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.core.ConcurrencyLimit:
    """
    Get a concurrency limit by tag.

    The `active slots` field contains a list of TaskRun IDs currently using a
    concurrency slot for the specified tag.
    """

    async with db.session_context() as session:
        model = await models.concurrency_limits.read_concurrency_limit_by_tag(
            session=session, tag=tag
        )

    if not model:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Concurrency limit not found"
        )
    return model


@router.post("/filter")
async def read_concurrency_limits(
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> Sequence[schemas.core.ConcurrencyLimit]:
    """
    Query for concurrency limits.

    For each concurrency limit the `active slots` field contains a list of TaskRun IDs
    currently using a concurrency slot for the specified tag.
    """
    async with db.session_context() as session:
        return await models.concurrency_limits.read_concurrency_limits(
            session=session,
            limit=limit,
            offset=offset,
        )


@router.post("/tag/{tag}/reset")
async def reset_concurrency_limit_by_tag(
    tag: str = Path(..., description="The tag name"),
    slot_override: Optional[List[UUID]] = Body(
        None,
        embed=True,
        description="Manual override for active concurrency limit slots.",
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    async with db.session_context(begin_transaction=True) as session:
        model = await models.concurrency_limits.reset_concurrency_limit_by_tag(
            session=session, tag=tag, slot_override=slot_override
        )
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Concurrency limit not found"
        )


@router.delete("/{id:uuid}")
async def delete_concurrency_limit(
    concurrency_limit_id: UUID = Path(
        ..., description="The concurrency limit id", alias="id"
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    async with db.session_context(begin_transaction=True) as session:
        result = await models.concurrency_limits.delete_concurrency_limit(
            session=session, concurrency_limit_id=concurrency_limit_id
        )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Concurrency limit not found"
        )


@router.delete("/tag/{tag}")
async def delete_concurrency_limit_by_tag(
    tag: str = Path(..., description="The tag name"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    async with db.session_context(begin_transaction=True) as session:
        result = await models.concurrency_limits.delete_concurrency_limit_by_tag(
            session=session, tag=tag
        )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Concurrency limit not found"
        )


class Abort(Exception):
    def __init__(self, reason: str):
        self.reason = reason


class Delay(Exception):
    def __init__(self, delay_seconds: float, reason: str):
        self.delay_seconds = delay_seconds
        self.reason = reason


@router.post("/increment")
async def increment_concurrency_limits_v1(
    names: List[str] = Body(..., description="The tags to acquire a slot for"),
    task_run_id: UUID = Body(
        ..., description="The ID of the task run acquiring the slot"
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[MinimalConcurrencyLimitResponse]:
    applied_limits = {}

    async with db.session_context(begin_transaction=True) as session:
        try:
            applied_limits = {}
            filtered_limits = (
                await concurrency_limits.filter_concurrency_limits_for_orchestration(
                    session, tags=names
                )
            )
            run_limits = {limit.tag: limit for limit in filtered_limits}
            for tag, cl in run_limits.items():
                limit = cl.concurrency_limit
                if limit == 0:
                    # limits of 0 will deadlock, and the transition needs to abort
                    for stale_tag in applied_limits.keys():
                        stale_limit = run_limits.get(stale_tag, None)
                        active_slots = set(stale_limit.active_slots)
                        active_slots.discard(str(task_run_id))
                        stale_limit.active_slots = list(active_slots)

                    raise Abort(
                        reason=(
                            f'The concurrency limit on tag "{tag}" is 0 and will '
                            "deadlock if the task tries to run again."
                        ),
                    )
                elif len(cl.active_slots) >= limit:
                    # if the limit has already been reached, delay the transition
                    for stale_tag in applied_limits.keys():
                        stale_limit = run_limits.get(stale_tag, None)
                        active_slots = set(stale_limit.active_slots)
                        active_slots.discard(str(task_run_id))
                        stale_limit.active_slots = list(active_slots)

                    raise Delay(
                        delay_seconds=PREFECT_TASK_RUN_TAG_CONCURRENCY_SLOT_WAIT_SECONDS.value(),
                        reason=f"Concurrency limit for the {tag} tag has been reached",
                    )
                else:
                    # log the TaskRun ID to active_slots
                    applied_limits[tag] = cl
                    active_slots = set(cl.active_slots)
                    active_slots.add(str(task_run_id))
                    cl.active_slots = list(active_slots)
        except Exception as e:
            for tag in applied_limits.keys():
                cl = await concurrency_limits.read_concurrency_limit_by_tag(
                    session, tag
                )
                active_slots = set(cl.active_slots)
                active_slots.discard(str(task_run_id))
                cl.active_slots = list(active_slots)

            if isinstance(e, Delay):
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=e.reason,
                    headers={"Retry-After": str(e.delay_seconds)},
                )
            elif isinstance(e, Abort):
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=e.reason,
                )
            else:
                raise
    return [
        MinimalConcurrencyLimitResponse(
            name=limit.tag, limit=limit.concurrency_limit, id=limit.id
        )
        for limit in applied_limits.values()
    ]


@router.post("/decrement")
async def decrement_concurrency_limits_v1(
    names: List[str] = Body(..., description="The tags to release a slot for"),
    task_run_id: UUID = Body(
        ..., description="The ID of the task run releasing the slot"
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    async with db.session_context(begin_transaction=True) as session:
        filtered_limits = (
            await concurrency_limits.filter_concurrency_limits_for_orchestration(
                session, tags=names
            )
        )
        run_limits = {limit.tag: limit for limit in filtered_limits}
        for tag, cl in run_limits.items():
            active_slots = set(cl.active_slots)
            active_slots.discard(str(task_run_id))
            cl.active_slots = list(active_slots)

    return [
        MinimalConcurrencyLimitResponse(
            name=limit.tag, limit=limit.concurrency_limit, id=limit.id
        )
        for limit in run_limits.values()
    ]
