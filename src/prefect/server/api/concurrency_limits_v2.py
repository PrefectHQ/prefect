from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

import anyio
from fastapi import Body, Depends, HTTPException, Path, status

import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.server.api.dependencies import LimitBody
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.events import ReceivedEvent
from prefect.server.events.filters import EventFilter
from prefect.server.events.storage import database
from prefect.server.schemas import actions
from prefect.server.utilities.schemas import PrefectBaseModel
from prefect.server.utilities.server import PrefectRouter

router = PrefectRouter(prefix="/v2/concurrency_limits", tags=["Concurrency Limits V2"])


async def get_all_events(
    event_filter: EventFilter,
    db: PrefectDBInterface,
    page_size: int = 50,
) -> List[ReceivedEvent]:
    all_events = []
    async with db.session_context() as session:
        events, total, next_token = await database.query_events(
            session=session,
            filter=event_filter,
            page_size=page_size,
        )
        all_events.extend(events)

        with anyio.move_on_after(5):
            while next_token:
                events, total, next_token = await database.query_next_page(
                    session=session,
                    page_token=next_token,
                )
                all_events.extend(events)
    return events


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_concurrency_limit_v2(
    concurrency_limit: actions.ConcurrencyLimitV2Create,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.core.ConcurrencyLimitV2:
    async with db.session_context(begin_transaction=True) as session:
        model = await models.concurrency_limits_v2.create_concurrency_limit(
            session=session, concurrency_limit=concurrency_limit
        )

    return schemas.core.ConcurrencyLimitV2.model_validate(model)


@router.get("/{id_or_name}")
async def read_concurrency_limit_v2(
    id_or_name: Union[UUID, str] = Path(
        ..., description="The ID or name of the concurrency limit", alias="id_or_name"
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.responses.GlobalConcurrencyLimitResponse:
    if isinstance(id_or_name, str):  # TODO: this seems like it shouldn't be necessary
        try:
            id_or_name = UUID(id_or_name)
        except ValueError:
            pass
    async with db.session_context() as session:
        if isinstance(id_or_name, UUID):
            model = await models.concurrency_limits_v2.read_concurrency_limit(
                session, concurrency_limit_id=id_or_name
            )
        else:
            model = await models.concurrency_limits_v2.read_concurrency_limit(
                session, name=id_or_name
            )

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Concurrency Limit not found"
        )

    return schemas.responses.GlobalConcurrencyLimitResponse.model_validate(model)


@router.post("/filter")
async def read_all_concurrency_limits_v2(
    limit: int = LimitBody(),
    offset: int = Body(0, ge=0),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.responses.GlobalConcurrencyLimitResponse]:
    async with db.session_context() as session:
        concurrency_limits = (
            await models.concurrency_limits_v2.read_all_concurrency_limits(
                session=session,
                limit=limit,
                offset=offset,
            )
        )

    return [
        schemas.responses.GlobalConcurrencyLimitResponse.model_validate(limit)
        for limit in concurrency_limits
    ]


@router.patch("/{id_or_name}", status_code=status.HTTP_204_NO_CONTENT)
async def update_concurrency_limit_v2(
    concurrency_limit: actions.ConcurrencyLimitV2Update,
    id_or_name: Union[UUID, str] = Path(
        ..., description="The ID or name of the concurrency limit", alias="id_or_name"
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    if isinstance(id_or_name, str):  # TODO: this seems like it shouldn't be necessary
        try:
            id_or_name = UUID(id_or_name)
        except ValueError:
            pass
    async with db.session_context(begin_transaction=True) as session:
        if isinstance(id_or_name, UUID):
            updated = await models.concurrency_limits_v2.update_concurrency_limit(
                session,
                concurrency_limit_id=id_or_name,
                concurrency_limit=concurrency_limit,
            )
        else:
            updated = await models.concurrency_limits_v2.update_concurrency_limit(
                session, name=id_or_name, concurrency_limit=concurrency_limit
            )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Concurrency Limit not found"
        )


@router.delete("/{id_or_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_concurrency_limit_v2(
    id_or_name: Union[UUID, str] = Path(
        ..., description="The ID or name of the concurrency limit", alias="id_or_name"
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    if isinstance(id_or_name, str):  # TODO: this seems like it shouldn't be necessary
        try:
            id_or_name = UUID(id_or_name)
        except ValueError:
            pass
    async with db.session_context(begin_transaction=True) as session:
        deleted = False
        if isinstance(id_or_name, UUID):
            deleted = await models.concurrency_limits_v2.delete_concurrency_limit(
                session, concurrency_limit_id=id_or_name
            )
        else:
            deleted = await models.concurrency_limits_v2.delete_concurrency_limit(
                session, name=id_or_name
            )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Concurrency Limit not found"
        )


class MinimalConcurrencyLimitResponse(PrefectBaseModel):
    id: UUID
    name: str
    limit: int


@router.post("/increment", status_code=status.HTTP_200_OK)
async def bulk_increment_active_slots(
    slots: int = Body(..., gt=0),
    names: List[str] = Body(..., min_items=1),
    mode: Literal["concurrency", "rate_limit"] = Body("concurrency"),
    create_if_missing: bool = Body(True),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[MinimalConcurrencyLimitResponse]:
    async with db.session_context(begin_transaction=True) as session:
        limits = [
            schemas.core.ConcurrencyLimitV2.model_validate(limit)
            for limit in (
                await models.concurrency_limits_v2.bulk_read_or_create_concurrency_limits(
                    session=session, names=names, create_if_missing=create_if_missing
                )
            )
        ]

        active_limits = [limit for limit in limits if bool(limit.active)]

        if any(limit.limit < slots for limit in active_limits):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Slots requested is greater than the limit",
            )

        non_decaying = [
            str(limit.name)
            for limit in active_limits
            if limit.slot_decay_per_second == 0.0
        ]

        if mode == "rate_limit" and non_decaying:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Only concurrency limits with slot decay can be used for "
                    "rate limiting. The following limits do not have a decay "
                    f"configured: {','.join(non_decaying)!r}"
                ),
            )
        acquired = await models.concurrency_limits_v2.bulk_increment_active_slots(
            session=session,
            concurrency_limit_ids=[limit.id for limit in active_limits],
            slots=slots,
        )

        if not acquired:
            await session.rollback()

    if acquired:
        return [
            MinimalConcurrencyLimitResponse(
                id=limit.id, name=str(limit.name), limit=limit.limit
            )
            for limit in limits
        ]
    else:
        async with db.session_context(begin_transaction=True) as session:
            await models.concurrency_limits_v2.bulk_update_denied_slots(
                session=session,
                concurrency_limit_ids=[limit.id for limit in active_limits],
                slots=slots,
            )

        def num_blocking_slots(limit: schemas.core.ConcurrencyLimitV2) -> float:
            if limit.slot_decay_per_second > 0.0:
                return slots + limit.denied_slots
            else:
                return (slots + limit.denied_slots) / limit.limit

        blocking_limit = max((limit for limit in active_limits), key=num_blocking_slots)
        blocking_slots = num_blocking_slots(blocking_limit)

        wait_time_per_slot = (
            blocking_limit.avg_slot_occupancy_seconds
            if blocking_limit.slot_decay_per_second == 0.0
            else (1.0 / blocking_limit.slot_decay_per_second)
        )

        retry_after = wait_time_per_slot * blocking_slots

        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            headers={
                "Retry-After": str(retry_after),
            },
        )


@router.post("/decrement", status_code=status.HTTP_200_OK)
async def bulk_decrement_active_slots(
    slots: int = Body(..., gt=0),
    names: List[str] = Body(..., min_items=1),
    occupancy_seconds: Optional[float] = Body(None, gt=0.0),
    create_if_missing: bool = Body(True),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[MinimalConcurrencyLimitResponse]:
    async with db.session_context(begin_transaction=True) as session:
        limits = (
            await models.concurrency_limits_v2.bulk_read_or_create_concurrency_limits(
                session=session, names=names, create_if_missing=create_if_missing
            )
        )

        if not limits:
            return []

        await models.concurrency_limits_v2.bulk_decrement_active_slots(
            session=session,
            concurrency_limit_ids=[limit.id for limit in limits if bool(limit.active)],
            slots=slots,
            occupancy_seconds=occupancy_seconds,
        )

    return [
        MinimalConcurrencyLimitResponse(
            id=limit.id, name=str(limit.name), limit=limit.limit
        )
        for limit in limits
    ]


ONE_HOUR = 60 * 60


@router.post("/active_owners", status_code=status.HTTP_200_OK)
async def read_concurrency_limit_owners(
    names: List[str] = Body(..., min_items=1),
    time_window: int = Body(ONE_HOUR, le=ONE_HOUR),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> Dict[str, Any]:
    async with db.session_context(begin_transaction=True) as session:
        limits = (
            await models.concurrency_limits_v2.bulk_read_or_create_concurrency_limits(
                session=session, names=names, create_if_missing=False
            )
        )

        if not limits:
            return {}

    # Create an EventFilter to find all concurrency limit acquired and released events for
    # resources matching the concurrency limit names in `limits`
    since = datetime.now() - timedelta(seconds=time_window)

    limit_ids = [f"prefect.concurrency-limit.{limit.id}" for limit in limits]
    acquired_filter = EventFilter(
        occurred={"since": since},
        event={"name": ["prefect.concurrency-limit.acquired"]},
        resource={"id": limit_ids},
    )
    released_filter = EventFilter(
        occurred={"since": since},
        event={"name": ["prefect.concurrency-limit.released"]},
        resource={"id": limit_ids},
    )

    acquired_events = await get_all_events(acquired_filter, db)
    released_events = await get_all_events(released_filter, db)
    limit_acquirers = defaultdict(set)
    seen_related_resources = {}

    for event in acquired_events:
        for r in event.related:
            if (
                r.role in ("flow-run", "task-run")
                and r.id not in limit_acquirers[event.resource.name]
            ):
                limit_acquirers[event.resource.name].add(r.id)
                seen_related_resources[r.id] = r

    for event in released_events:
        print(event)
        for r in event.related:
            if r.role in ("flow-run", "task-run"):
                limit_acquirers[event.resource.name].remove(r.id)

    return {
        limit: [
            {
                "id": resource_id.split(".")[2],
                "type": seen_related_resources[resource_id].role,
                "name": seen_related_resources[resource_id].name,
            }
            for resource_id in limit_acquirers.get(limit, [])
        ]
        for limit in limit_acquirers
    }
