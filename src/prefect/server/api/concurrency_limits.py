"""
Routes for interacting with concurrency limit objects.
"""
from typing import List, Optional
from uuid import UUID
import sqlalchemy as sa
import logging
import uuid
import redis.asyncio as redis
import time


import pendulum
from fastapi import Body, Depends, HTTPException, Path, Response, status

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.utilities.server import PrefectRouter

router = PrefectRouter(prefix="/concurrency_limits", tags=["Concurrency Limits"])

logger = logging.getLogger(__name__)


@router.post("/")
async def create_concurrency_limit(
    concurrency_limit: schemas.actions.ConcurrencyLimitCreate,
    response: Response,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.core.ConcurrencyLimit:
    # hydrate the input model into a full model
    concurrency_limit_model = schemas.core.ConcurrencyLimit(**concurrency_limit.dict())

    async with db.session_context(begin_transaction=True) as session:
        model = await models.concurrency_limits.create_concurrency_limit(
            session=session, concurrency_limit=concurrency_limit_model
        )

    if model.created >= pendulum.now():
        response.status_code = status.HTTP_201_CREATED

    return model


@router.get("/{id}")
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
) -> List[schemas.core.ConcurrencyLimit]:
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
):
    async with db.session_context(begin_transaction=True) as session:
        model = await models.concurrency_limits.reset_concurrency_limit_by_tag(
            session=session, tag=tag, slot_override=slot_override
        )
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Concurrency limit not found"
        )


@router.delete("/{id}")
async def delete_concurrency_limit(
    concurrency_limit_id: UUID = Path(
        ..., description="The concurrency limit id", alias="id"
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
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
):
    async with db.session_context(begin_transaction=True) as session:
        result = await models.concurrency_limits.delete_concurrency_limit_by_tag(
            session=session, tag=tag
        )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Concurrency limit not found"
        )


# Redis implementation
# --------------------
redis_pool = redis.ConnectionPool.from_url(
    "redis://localhost:16379", decode_responses=True
)


@router.post("/increment/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def increment_active_slots_redis(
    name: str = Path(..., description="The name of the concurrency_limit"),
    slots: int = Body(..., description="The number of slots to increment"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    async with db.session_context() as session:
        model = await models.concurrency_limits.read_concurrency_limit_by_tag(
            session=session, tag=name
        )

    timestamp = time.time()

    redis_conn = redis.Redis(connection_pool=redis_pool)

    while True:
        async with redis_conn.pipeline(transaction=True) as pipe:
            try:
                await pipe.watch(model.tag)

                count = await redis_conn.zcard(model.tag)

                if count + slots <= model.concurrency_limit:
                    pipe.multi()
                    for _ in range(slots):
                        slot_id = str(uuid.uuid4())
                        await pipe.zadd(model.tag, {slot_id: timestamp})
                    await pipe.execute()
                    return
                else:
                    raise HTTPException(status_code=status.HTTP_202_ACCEPTED)

            except redis.WatchError:
                continue


@router.post("/decrement/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def decrement_active_slots_redis(
    name: str = Path(..., description="The name of the concurrency_limit"),
    slots: int = Body(..., description="The number of slots to increment"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    redis_conn = redis.Redis(connection_pool=redis_pool)
    await redis_conn.zpopmin(name, slots)


# Database implementation
# --------------------


@router.post("/increment/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def increment_active_slots(
    name: str = Path(..., description="The name of the concurrency_limit"),
    slots: int = Body(..., description="The number of slots to increment"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        query = (
            sa.update(db.ConcurrencyLimit)
            .where(
                sa.and_(
                    db.ConcurrencyLimit.tag == name,
                    db.ConcurrencyLimit.slots + slots
                    <= db.ConcurrencyLimit.concurrency_limit,
                )
            )
            .values(slots=db.ConcurrencyLimit.slots + slots)
        )

        result = await session.execute(query)
        rowcount = result.rowcount

        if rowcount == 0:
            # This should probably use a 423 or similar, but locust.io tracks
            # them as failures, so this gives a better output for the load
            # test.
            raise HTTPException(status_code=status.HTTP_202_ACCEPTED)


@router.post("/decrement/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def decrement_active_slots(
    name: str = Path(..., description="The name of the concurrency_limit"),
    slots: int = Body(..., description="The number of slots to increment"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        query = (
            sa.update(db.ConcurrencyLimit)
            .where(db.ConcurrencyLimit.tag == name)
            .values(slots=db.ConcurrencyLimit.slots - slots)
        )

        await session.execute(query)
