"""
Routes for interacting with concurrency limit objects.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence
from uuid import UUID

from fastapi import Body, Depends, HTTPException, Path, Response, status

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.exceptions import PrefectHTTPStatusError
from prefect.server.api.concurrency_limits_v2 import MinimalConcurrencyLimitResponse
from prefect.server.concurrency.lease_storage import (
    ConcurrencyLimitLeaseMetadata,
    get_concurrency_lease_storage,
)
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.models import concurrency_limits
from prefect.server.models import concurrency_limits_v2 as cl_v2_models
from prefect.server.utilities.server import PrefectRouter
from prefect.settings import PREFECT_TASK_RUN_TAG_CONCURRENCY_SLOT_WAIT_SECONDS
from prefect.types._datetime import now
from prefect.utilities.collections import distinct

router: PrefectRouter = PrefectRouter(
    prefix="/concurrency_limits", tags=["Concurrency Limits"]
)


def _adapter_enabled() -> bool:
    """Adapter is always enabled in Server."""
    return True


async def _get_active_slots_from_leases(limit_id: UUID) -> list[str]:
    """Extract task_run IDs from active leases for a given limit."""
    lease_storage = get_concurrency_lease_storage()
    active_holders: list[str] = []

    # Prefer storage-provided enumeration when available
    list_fn = getattr(lease_storage, "list_holders_for_limit", None)
    holders = []
    if callable(list_fn):
        holders = await list_fn(limit_id)  # type: ignore[misc]
    else:
        # Fallback: scan active leases
        for lid in await lease_storage.read_active_lease_ids(limit=1024):
            lease = await lease_storage.read_lease(lid)
            if not lease or limit_id not in lease.resource_ids:
                continue
            if lease.metadata and getattr(lease.metadata, "holder", None):
                holders.append(lease.metadata.holder)

    for holder in holders:
        # Support both shapes:
        # 1) {"type": "task_run", "id": "..."}
        # 2) {"holder": {"type": "task_run", "id": "..."}, "slots": N}
        if isinstance(holder, dict):
            h = holder.get("holder") if "holder" in holder else holder
            if isinstance(h, dict) and h.get("type") == "task_run" and h.get("id"):
                active_holders.append(str(h["id"]))

    return active_holders


async def _find_lease_for_task_run(
    task_run_id: UUID, tags: list[str], db: PrefectDBInterface
) -> UUID | None:
    """Find the lease ID for a given task run."""
    lease_storage = get_concurrency_lease_storage()

    # Convert tags to V2 names to check relevant limits
    v2_names = [f"tag:{tag}" for tag in tags]

    async with db.session_context() as session:
        limit_ids = []
        for v2_name in v2_names:
            model = await cl_v2_models.read_concurrency_limit(
                session=session, name=v2_name
            )
            if model:
                limit_ids.append(model.id)

    if not limit_ids:
        return None

    # Try direct per-limit holder search if storage exposes helpers; else scan
    list_fn = getattr(lease_storage, "list_holders_for_limit", None)
    if callable(list_fn):
        desired = {"type": "task_run", "id": str(task_run_id)}
        for limit_id in limit_ids:
            holders = await list_fn(limit_id)  # type: ignore[misc]
            # holders may be shape 1) {"type","id"} or 2) {"holder": {...}, "slots": N}
            for h in holders:
                payload = h.get("holder", h) if isinstance(h, dict) else None
                if isinstance(payload, dict) and payload == desired:
                    # Read a lease id by scanning active leases for this limit
                    for lid in await lease_storage.read_active_lease_ids(limit=1000):
                        lease = await lease_storage.read_lease(lid)
                        if lease and limit_id in lease.resource_ids:
                            inner = (
                                getattr(lease.metadata, "holder", None)
                                if lease.metadata
                                else None
                            )
                            if inner is not None and hasattr(inner, "model_dump"):
                                inner = inner.model_dump(mode="json")  # type: ignore[attr-defined]
                            if isinstance(inner, dict) and inner == desired:
                                return lid

    # Fallback: scan active leases
    active_leases = await lease_storage.read_active_lease_ids(limit=1000)

    for lease_id in active_leases:
        lease = await lease_storage.read_lease(lease_id)
        if lease and lease.metadata and getattr(lease.metadata, "holder", None):
            holder = lease.metadata.holder
            if holder is not None and hasattr(holder, "model_dump"):
                holder = holder.model_dump(mode="json")  # type: ignore[attr-defined]
            if (
                isinstance(holder, dict)
                and holder.get("type") == "task_run"
                and holder.get("id") == str(task_run_id)
            ):
                # Check if this lease is for one of the requested limits
                if any(lid in lease.resource_ids for lid in limit_ids):
                    return lease_id

    return None


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
    if _adapter_enabled():
        # V1→V2 adapter: Create/update V2 limit with tag: prefix
        v2_name = f"tag:{concurrency_limit.tag}"

        async with db.session_context(begin_transaction=True) as session:
            # Check if exists for upsert behavior
            existing = await cl_v2_models.read_concurrency_limit(
                session=session, name=v2_name
            )

            if existing:
                # Update existing (V1 upsert behavior)
                await cl_v2_models.update_concurrency_limit(
                    session=session,
                    concurrency_limit_id=existing.id,
                    concurrency_limit=schemas.actions.ConcurrencyLimitV2Update(
                        limit=concurrency_limit.concurrency_limit
                    ),
                )
                model = existing
                model.limit = concurrency_limit.concurrency_limit
            else:
                # Create new
                model = await cl_v2_models.create_concurrency_limit(
                    session=session,
                    concurrency_limit=schemas.core.ConcurrencyLimitV2(
                        name=v2_name,
                        limit=concurrency_limit.concurrency_limit,
                        active=True,
                    ),
                )
                response.status_code = status.HTTP_201_CREATED

        # Get active slots from leases
        active_slots = await _get_active_slots_from_leases(model.id)

        # Convert to V1 response format
        return schemas.core.ConcurrencyLimit(
            id=model.id,
            tag=concurrency_limit.tag,
            concurrency_limit=model.limit,
            active_slots=active_slots,
            created=model.created,
            updated=model.updated,
        )

    # Original V1 implementation
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
    if _adapter_enabled():
        # Try V2 by id first; if it's a tag-based limit, convert to V1 shape
        async with db.session_context() as session:
            v2_limit = await cl_v2_models.read_concurrency_limit(
                session=session, concurrency_limit_id=concurrency_limit_id
            )

            if v2_limit and v2_limit.name.startswith("tag:"):
                active_slots = await _get_active_slots_from_leases(v2_limit.id)
                return schemas.core.ConcurrencyLimit(
                    id=v2_limit.id,
                    tag=v2_limit.name.removeprefix("tag:"),
                    concurrency_limit=v2_limit.limit,
                    active_slots=active_slots,
                    created=v2_limit.created,
                    updated=v2_limit.updated,
                )

        # Fall back to V1 read
        async with db.session_context() as session:
            model = await models.concurrency_limits.read_concurrency_limit(
                session=session, concurrency_limit_id=concurrency_limit_id
            )
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Concurrency limit not found",
            )
        return model

    # Original V1 implementation
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
    if _adapter_enabled():
        # V1→V2 adapter: Read V2 limit and populate active_slots from leases
        v2_name = f"tag:{tag}"

        async with db.session_context() as session:
            model = await cl_v2_models.read_concurrency_limit(
                session=session, name=v2_name
            )

        if not model:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Concurrency limit not found"
            )

        # Get active slots from leases
        active_slots = await _get_active_slots_from_leases(model.id)

        return schemas.core.ConcurrencyLimit(
            id=model.id,
            tag=tag,
            concurrency_limit=model.limit,
            active_slots=active_slots,
            created=model.created,
            updated=model.updated,
        )

    # Original V1 implementation
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
    if _adapter_enabled():
        # V1→V2 adapter: Merge V1 limits and V2 tag: limits, dedupe by tag
        async with db.session_context() as session:
            v1_all = await models.concurrency_limits.read_concurrency_limits(
                session=session, limit=limit + offset, offset=0
            )
            v2_all = await cl_v2_models.read_all_concurrency_limits(
                session=session, limit=limit + offset, offset=0
            )

        converted_v2: list[schemas.core.ConcurrencyLimit] = []
        for v2_limit in v2_all:
            if not v2_limit.name.startswith("tag:"):
                continue
            tag = v2_limit.name.removeprefix("tag:")
            active_slots = await _get_active_slots_from_leases(v2_limit.id)
            converted_v2.append(
                schemas.core.ConcurrencyLimit(
                    id=v2_limit.id,
                    tag=tag,
                    concurrency_limit=v2_limit.limit,
                    active_slots=active_slots,
                    created=v2_limit.created,
                    updated=v2_limit.updated,
                )
            )

        # Prefer V2 entries by placing them first, then dedupe by tag
        combined = list(distinct(converted_v2 + list(v1_all), key=lambda o: o.tag))
        return combined[offset : offset + limit]

    # Original V1 implementation
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
    if _adapter_enabled():
        # V1→V2 adapter: Reset leases for V2 limit
        v2_name = f"tag:{tag}"

        async with db.session_context(begin_transaction=True) as session:
            model = await cl_v2_models.read_concurrency_limit(
                session=session, name=v2_name
            )

            if not model:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Concurrency limit not found",
                )

            # Get lease storage
            lease_storage = get_concurrency_lease_storage()

            # Revoke all existing leases for this limit
            active_leases = await lease_storage.read_active_lease_ids(limit=1000)
            for lease_id in active_leases:
                lease = await lease_storage.read_lease(lease_id)
                if lease and model.id in lease.resource_ids:
                    await lease_storage.revoke_lease(lease_id)

            # Create new leases for slot_override if provided
            if slot_override:
                for task_run_id in slot_override:
                    holder = {
                        "type": "task_run",
                        "id": str(task_run_id),
                    }
                    # First increment active slots, then create corresponding lease
                    acquired = await cl_v2_models.bulk_increment_active_slots(
                        session=session,
                        concurrency_limit_ids=[model.id],
                        slots=1,
                    )
                    if acquired:
                        await lease_storage.create_lease(
                            resource_ids=[model.id],
                            ttl=timedelta(days=36500),  # ~100 years
                            metadata=ConcurrencyLimitLeaseMetadata(
                                slots=1, holder=holder
                            ),
                        )
        return

    # Original V1 implementation
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
    # Note: We don't adapter the ID-based delete since V1 IDs won't match V2
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
    if _adapter_enabled():
        # V1→V2 adapter: Delete V2 limit and clean up leases; also delete any V1 record
        v2_name = f"tag:{tag}"

        async with db.session_context(begin_transaction=True) as session:
            model = await cl_v2_models.read_concurrency_limit(
                session=session, name=v2_name
            )

            if model:
                lease_storage = get_concurrency_lease_storage()
                active_leases = await lease_storage.read_active_lease_ids(limit=1000)
                for lease_id in active_leases:
                    lease = await lease_storage.read_lease(lease_id)
                    if lease and model.id in lease.resource_ids:
                        await lease_storage.revoke_lease(lease_id)

                v2_deleted = await cl_v2_models.delete_concurrency_limit(
                    session=session, concurrency_limit_id=model.id
                )
            else:
                v2_deleted = False

        async with db.session_context(begin_transaction=True) as session:
            v1_deleted = (
                await models.concurrency_limits.delete_concurrency_limit_by_tag(
                    session=session, tag=tag
                )
            )

        if not (v2_deleted or v1_deleted):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Concurrency limit not found",
            )
        return

    # Original V1 implementation
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
    if _adapter_enabled():
        # V1→V2 adapter: Use V2 increment-with-lease only when ALL V2 tag: limits exist
        from prefect.client.orchestration import get_client

        v2_names = [f"tag:{tag}" for tag in names]

        # Check for existence of all V2 limits
        async with db.session_context() as session:
            existing_v2 = []
            for v2_name in v2_names:
                model = await cl_v2_models.read_concurrency_limit(
                    session=session, name=v2_name
                )
                if model:
                    existing_v2.append(model)

        if len(existing_v2) == len(v2_names):
            holder = {
                "type": "task_run",
                "id": str(task_run_id),
            }

            try:
                async with get_client() as client:
                    response = await client.increment_concurrency_slots_with_lease(
                        names=v2_names,
                        slots=1,
                        mode="concurrency",
                        lease_duration=86400,  # 24 hours (max allowed)
                        holder=holder,
                    )

                data = response.json()
                return [
                    MinimalConcurrencyLimitResponse(
                        id=limit["id"],
                        name=limit["name"].removeprefix("tag:"),
                        limit=limit["limit"],
                    )
                    for limit in data.get("limits", [])
                ]
            except PrefectHTTPStatusError as exc:
                if exc.response.status_code == status.HTTP_423_LOCKED:
                    retry_after = exc.response.headers.get("Retry-After")
                    if retry_after:
                        raise HTTPException(
                            status_code=status.HTTP_423_LOCKED,
                            detail="Concurrency limit reached",
                            headers={"Retry-After": retry_after},
                        )
                    raise HTTPException(
                        status_code=status.HTTP_423_LOCKED,
                        detail="Concurrency limit is 0",
                    )
                raise

    # Original V1 implementation
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
) -> List[MinimalConcurrencyLimitResponse]:
    if _adapter_enabled():
        # V1→V2 adapter: Find and release the lease for this task run
        lease_id = await _find_lease_for_task_run(task_run_id, names, db)
        if lease_id:
            # Perform server-side decrement-by-lease
            lease_storage = get_concurrency_lease_storage()
            lease = await lease_storage.read_lease(lease_id)
            if lease:
                occupancy_seconds = (
                    datetime.now(timezone.utc) - lease.created_at
                ).total_seconds()
                async with db.session_context(begin_transaction=True) as session:
                    await cl_v2_models.bulk_decrement_active_slots(
                        session=session,
                        concurrency_limit_ids=lease.resource_ids,
                        slots=lease.metadata.slots if lease.metadata else 0,
                        occupancy_seconds=occupancy_seconds,
                    )
                await lease_storage.revoke_lease(lease_id)

        # Return current limits (matching V1 behavior)
        v2_names = [f"tag:{tag}" for tag in names]
        limits = []

        async with db.session_context() as session:
            for v2_name, tag in zip(v2_names, names):
                model = await cl_v2_models.read_concurrency_limit(
                    session=session, name=v2_name
                )
                if model:
                    limits.append(
                        MinimalConcurrencyLimitResponse(
                            id=model.id, name=tag, limit=model.limit
                        )
                    )

        return limits

    # Original V1 implementation
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
