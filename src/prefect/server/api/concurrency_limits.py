"""
Routes for interacting with concurrency limit objects.

This module provides a V1 API adapter that routes requests to the V2 concurrency
system. After the migration, V1 limits are converted to V2, but the V1 API
continues to work for backward compatibility.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import List, Optional, Sequence
from uuid import UUID

from fastapi import Body, Depends, HTTPException, Path, Response, status

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.logging.loggers import get_logger
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
from prefect.types._concurrency import ConcurrencyLeaseHolder

router: PrefectRouter = PrefectRouter(
    prefix="/concurrency_limits", tags=["Concurrency Limits"]
)
logger: logging.Logger = get_logger(__name__)
# V1 clients cannot renew leases; use a long TTL
V1_LEASE_TTL = timedelta(days=100 * 365)  # ~100 years


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
    # Always create V2 limits (no V1 record)
    v2_name = f"tag:{concurrency_limit.tag}"

    async with db.session_context(begin_transaction=True) as session:
        # Check if V2 already exists (upsert behavior)
        existing = await cl_v2_models.read_concurrency_limit(
            session=session, name=v2_name
        )

        if existing:
            # Update existing V2 limit
            await cl_v2_models.update_concurrency_limit(
                session=session,
                concurrency_limit_id=existing.id,
                concurrency_limit=schemas.actions.ConcurrencyLimitV2Update(
                    limit=concurrency_limit.concurrency_limit
                ),
            )
            model = existing
            model.limit = concurrency_limit.concurrency_limit
            response.status_code = status.HTTP_200_OK
        else:
            # Create new V2 limit
            model = await cl_v2_models.create_concurrency_limit(
                session=session,
                concurrency_limit=schemas.core.ConcurrencyLimitV2(
                    name=v2_name,
                    limit=concurrency_limit.concurrency_limit,
                    active=True,
                ),
            )
            response.status_code = status.HTTP_201_CREATED

    # Return V1 format
    lease_storage = get_concurrency_lease_storage()
    holders = await lease_storage.list_holders_for_limit(model.id)
    active_slots = [h.id for _, h in holders if h.type == "task_run"]

    return schemas.core.ConcurrencyLimit(
        id=model.id,
        tag=concurrency_limit.tag,
        concurrency_limit=model.limit,
        active_slots=active_slots,
        created=model.created,
        updated=model.updated,
    )


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
    # Try V2 first
    async with db.session_context() as session:
        v2_limit = await cl_v2_models.read_concurrency_limit(
            session=session, concurrency_limit_id=concurrency_limit_id
        )

        if v2_limit and v2_limit.name.startswith("tag:"):
            tag = v2_limit.name.removeprefix("tag:")
            lease_storage = get_concurrency_lease_storage()
            holders = await lease_storage.list_holders_for_limit(v2_limit.id)
            active_slots = [h.id for _, h in holders if h.type == "task_run"]

            return schemas.core.ConcurrencyLimit(
                id=v2_limit.id,
                tag=tag,
                concurrency_limit=v2_limit.limit,
                active_slots=active_slots,
                created=v2_limit.created,
                updated=v2_limit.updated,
            )

    # Fall back to V1 (for pre-migration compatibility)
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
    # Try V2 first
    v2_name = f"tag:{tag}"

    async with db.session_context() as session:
        model = await cl_v2_models.read_concurrency_limit(session=session, name=v2_name)

    if model:
        lease_storage = get_concurrency_lease_storage()
        holders = await lease_storage.list_holders_for_limit(model.id)
        active_slots = [h.id for _, h in holders if h.type == "task_run"]

        return schemas.core.ConcurrencyLimit(
            id=model.id,
            tag=tag,
            concurrency_limit=model.limit,
            active_slots=active_slots,
            created=model.created,
            updated=model.updated,
        )

    # Fall back to V1 (for pre-migration compatibility)
    async with db.session_context() as session:
        v1_model = await models.concurrency_limits.read_concurrency_limit_by_tag(
            session=session, tag=tag
        )
    if not v1_model:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Concurrency limit not found"
        )
    return v1_model


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
    # Get both V1 and V2, then merge
    async with db.session_context() as session:
        v1_limits = await models.concurrency_limits.read_concurrency_limits(
            session=session, limit=limit + offset, offset=0
        )
        v2_limits = await cl_v2_models.read_all_concurrency_limits(
            session=session, limit=limit + offset, offset=0
        )

    # Convert V2 to V1 format
    converted_v2: list[schemas.core.ConcurrencyLimit] = []
    lease_storage = get_concurrency_lease_storage()

    for v2_limit in v2_limits:
        if not v2_limit.name.startswith("tag:"):
            continue
        tag = v2_limit.name.removeprefix("tag:")
        holders = await lease_storage.list_holders_for_limit(v2_limit.id)
        active_slots = [h.id for _, h in holders if h.type == "task_run"]

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

    # Merge and deduplicate by tag (prefer V2)
    seen_tags = {cl.tag for cl in converted_v2}
    combined = converted_v2 + [cl for cl in v1_limits if cl.tag not in seen_tags]

    return combined[offset : offset + limit]


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
    # Try V2 first
    v2_name = f"tag:{tag}"

    async with db.session_context(begin_transaction=True) as session:
        model = await cl_v2_models.read_concurrency_limit(session=session, name=v2_name)

        if model:
            # Revoke all existing leases
            lease_storage = get_concurrency_lease_storage()

            # Keep fetching and revoking in batches until all are gone
            batch_size = 100
            offset = 0
            while True:
                active_lease_ids = await lease_storage.read_active_lease_ids(
                    limit=batch_size, offset=offset
                )
                if not active_lease_ids:
                    break

                revoked_any = False
                for lease_id in active_lease_ids:
                    lease = await lease_storage.read_lease(lease_id)
                    if lease and model.id in lease.resource_ids:
                        await lease_storage.revoke_lease(lease_id)
                        revoked_any = True

                # If we didn't revoke any in this batch, we're done with this limit
                if not revoked_any:
                    offset += batch_size
                else:
                    # Start from beginning since we modified the list
                    offset = 0

            # Create new leases for slot_override if provided
            if slot_override:
                for task_run_id in slot_override:
                    await cl_v2_models.bulk_increment_active_slots(
                        session=session,
                        concurrency_limit_ids=[model.id],
                        slots=1,
                    )
                    await lease_storage.create_lease(
                        resource_ids=[model.id],
                        ttl=V1_LEASE_TTL,
                        metadata=ConcurrencyLimitLeaseMetadata(
                            slots=1,
                            holder=ConcurrencyLeaseHolder(
                                type="task_run", id=task_run_id
                            ),
                        ),
                    )
            return

        # Fall back to V1
        model = await models.concurrency_limits.reset_concurrency_limit_by_tag(
            session=session, tag=tag, slot_override=slot_override
        )
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Concurrency limit not found",
            )


@router.delete("/{id:uuid}")
async def delete_concurrency_limit(
    concurrency_limit_id: UUID = Path(
        ..., description="The concurrency limit id", alias="id"
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    # Try V2 first
    async with db.session_context(begin_transaction=True) as session:
        v2 = await cl_v2_models.read_concurrency_limit(
            session=session, concurrency_limit_id=concurrency_limit_id
        )
        if v2:
            # Clean up leases
            lease_storage = get_concurrency_lease_storage()

            # Keep fetching and revoking in batches until all are gone
            batch_size = 100
            offset = 0
            while True:
                active_lease_ids = await lease_storage.read_active_lease_ids(
                    limit=batch_size, offset=offset
                )
                if not active_lease_ids:
                    break

                revoked_any = False
                for lease_id in active_lease_ids:
                    lease = await lease_storage.read_lease(lease_id)
                    if lease and v2.id in lease.resource_ids:
                        await lease_storage.revoke_lease(lease_id)
                        revoked_any = True

                # If we didn't revoke any in this batch, we're done with this limit
                if not revoked_any:
                    offset += batch_size
                else:
                    # Start from beginning since we modified the list
                    offset = 0

            # Delete V2
            await cl_v2_models.delete_concurrency_limit(
                session=session, concurrency_limit_id=v2.id
            )
            return

    # Try V1
    async with db.session_context(begin_transaction=True) as session:
        v1_deleted = await models.concurrency_limits.delete_concurrency_limit(
            session=session, concurrency_limit_id=concurrency_limit_id
        )
        if not v1_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Concurrency limit not found",
            )


@router.delete("/tag/{tag}")
async def delete_concurrency_limit_by_tag(
    tag: str = Path(..., description="The tag name"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    # Try V2 first
    v2_name = f"tag:{tag}"
    async with db.session_context(begin_transaction=True) as session:
        model = await cl_v2_models.read_concurrency_limit(session=session, name=v2_name)
        if model:
            # Clean up leases
            lease_storage = get_concurrency_lease_storage()

            # Keep fetching and revoking in batches until all are gone
            batch_size = 100
            offset = 0
            while True:
                active_lease_ids = await lease_storage.read_active_lease_ids(
                    limit=batch_size, offset=offset
                )
                if not active_lease_ids:
                    break

                revoked_any = False
                for lease_id in active_lease_ids:
                    lease = await lease_storage.read_lease(lease_id)
                    if lease and model.id in lease.resource_ids:
                        await lease_storage.revoke_lease(lease_id)
                        revoked_any = True

                # If we didn't revoke any in this batch, we're done with this limit
                if not revoked_any:
                    offset += batch_size
                else:
                    # Start from beginning since we modified the list
                    offset = 0

            # Delete V2
            await cl_v2_models.delete_concurrency_limit(
                session=session, concurrency_limit_id=model.id
            )
            return

    # Try V1
    async with db.session_context(begin_transaction=True) as session:
        v1_deleted = await models.concurrency_limits.delete_concurrency_limit_by_tag(
            session=session, tag=tag
        )
        if not v1_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Concurrency limit not found",
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
    """
    Increment concurrency limits for the given tags.

    During migration, this handles both V1 and V2 limits to support mixed states.
    Post-migration, it only uses V2 with lease-based concurrency.
    """
    results = []
    v2_names = [f"tag:{tag}" for tag in names]

    async with db.session_context(begin_transaction=True) as session:
        # Get V2 limits
        v2_limits = await cl_v2_models.bulk_read_concurrency_limits(
            session=session, names=v2_names
        )
        v2_by_name = {limit.name: limit for limit in v2_limits}

        # Get V1 limits (for pre-migration compatibility)
        v1_limits = (
            await concurrency_limits.filter_concurrency_limits_for_orchestration(
                session, tags=names
            )
        )
        v1_by_tag = {limit.tag: limit for limit in v1_limits}

        # Check all zero limits upfront before acquiring any
        for tag in names:
            v2_limit = v2_by_name.get(f"tag:{tag}")
            v1_limit = v1_by_tag.get(tag)

            if v2_limit and v2_limit.limit == 0:
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=f'The concurrency limit on tag "{tag}" is 0 and will deadlock if the task tries to run again.',
                )
            elif v1_limit and v1_limit.concurrency_limit == 0:
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=f'The concurrency limit on tag "{tag}" is 0 and will deadlock if the task tries to run again.',
                )

        # Collect V2 limits to acquire in bulk
        v2_to_acquire = []
        v2_tags_map = {}  # Map limit IDs to tags for results

        # Check V1 limits availability upfront
        v1_to_acquire = []

        for tag in names:
            v2_limit = v2_by_name.get(f"tag:{tag}")
            v1_limit = v1_by_tag.get(tag)

            if v2_limit and v2_limit.active:
                v2_to_acquire.append(v2_limit.id)
                v2_tags_map[v2_limit.id] = tag
            elif v1_limit:
                # Check V1 limit availability
                if len(v1_limit.active_slots) >= v1_limit.concurrency_limit:
                    raise HTTPException(
                        status_code=status.HTTP_423_LOCKED,
                        detail=f"Concurrency limit for the {tag} tag has been reached",
                        headers={
                            "Retry-After": str(
                                PREFECT_TASK_RUN_TAG_CONCURRENCY_SLOT_WAIT_SECONDS.value()
                            )
                        },
                    )
                v1_to_acquire.append(v1_limit)

        # Bulk acquire all V2 limits at once
        acquired_v2_ids = []
        if v2_to_acquire:
            acquired = await cl_v2_models.bulk_increment_active_slots(
                session=session,
                concurrency_limit_ids=v2_to_acquire,
                slots=1,
            )
            if not acquired:
                # Find which limit was at capacity
                for lid in v2_to_acquire:
                    tag = v2_tags_map[lid]
                    raise HTTPException(
                        status_code=status.HTTP_423_LOCKED,
                        detail=f"Concurrency limit for the {tag} tag has been reached",
                        headers={
                            "Retry-After": str(
                                PREFECT_TASK_RUN_TAG_CONCURRENCY_SLOT_WAIT_SECONDS.value()
                            )
                        },
                    )
            acquired_v2_ids = v2_to_acquire

            # Add V2 results
            for lid in acquired_v2_ids:
                tag = v2_tags_map[lid]
                limit = v2_by_name[f"tag:{tag}"]
                results.append(
                    MinimalConcurrencyLimitResponse(
                        id=limit.id, name=tag, limit=limit.limit
                    )
                )

        # Apply V1 increments (already checked availability)
        for v1_limit in v1_to_acquire:
            active_slots = set(v1_limit.active_slots)
            active_slots.add(str(task_run_id))
            v1_limit.active_slots = list(active_slots)
            results.append(
                MinimalConcurrencyLimitResponse(
                    id=v1_limit.id, name=v1_limit.tag, limit=v1_limit.concurrency_limit
                )
            )

    # Create lease for V2 limits
    if acquired_v2_ids:
        lease_storage = get_concurrency_lease_storage()
        await lease_storage.create_lease(
            resource_ids=acquired_v2_ids,
            ttl=V1_LEASE_TTL,
            metadata=ConcurrencyLimitLeaseMetadata(
                slots=1,
                holder=ConcurrencyLeaseHolder(type="task_run", id=task_run_id),
            ),
        )

    return results


@router.post("/decrement")
async def decrement_concurrency_limits_v1(
    names: List[str] = Body(..., description="The tags to release a slot for"),
    task_run_id: UUID = Body(
        ..., description="The ID of the task run releasing the slot"
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[MinimalConcurrencyLimitResponse]:
    """
    Decrement concurrency limits for the given tags.

    Finds and revokes the lease for V2 limits or decrements V1 active slots.
    Returns the list of limits that were decremented.
    """
    results: list[MinimalConcurrencyLimitResponse] = []
    lease_storage = get_concurrency_lease_storage()
    v2_names = [f"tag:{tag}" for tag in names]

    async with db.session_context(begin_transaction=True) as session:
        # Bulk read V2 limits
        v2_limits = await cl_v2_models.bulk_read_concurrency_limits(
            session=session, names=v2_names
        )
        v2_by_name = {limit.name: limit for limit in v2_limits}

        # Find and revoke lease for V2 limits
        if v2_limits:
            leases_ids_to_revoke: set[UUID] = set()

            for limit in v2_limits:
                holders = await lease_storage.list_holders_for_limit(limit.id)
                for lease_id, holder in holders:
                    if holder.id == task_run_id:
                        lease = await lease_storage.read_lease(lease_id)
                        if lease:
                            leases_ids_to_revoke.add(lease.id)

            for lease_id in leases_ids_to_revoke:
                lease = await lease_storage.read_lease(lease_id)
                if lease:
                    await cl_v2_models.bulk_decrement_active_slots(
                        session=session,
                        concurrency_limit_ids=lease.resource_ids,
                        slots=lease.metadata.slots if lease.metadata else 0,
                    )
                    await lease_storage.revoke_lease(lease.id)
                else:
                    logger.warning(f"Lease {lease_id} not found during decrement")

            results.extend(
                [
                    MinimalConcurrencyLimitResponse(
                        id=limit.id, name=limit.name, limit=limit.limit
                    )
                    for limit in v2_limits
                ]
            )

        # Handle V1 decrements (for pre-migration compatibility)
        v1_limits = (
            await concurrency_limits.filter_concurrency_limits_for_orchestration(
                session, tags=names
            )
        )
        for cl in v1_limits:
            # Skip if already handled as V2
            v2_name = f"tag:{cl.tag}"
            if v2_name not in v2_by_name:
                active_slots = set(cl.active_slots)
                if str(task_run_id) in active_slots:
                    active_slots.discard(str(task_run_id))
                    cl.active_slots = list(active_slots)
                    results.append(
                        MinimalConcurrencyLimitResponse(
                            id=cl.id, name=cl.tag, limit=cl.concurrency_limit
                        )
                    )

    return results
