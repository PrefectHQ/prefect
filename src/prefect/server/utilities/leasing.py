from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Generic, Protocol, TypeVar
from uuid import UUID, uuid4

T = TypeVar("T")


@dataclass
class ResourceLease(Generic[T]):
    resource_ids: list[UUID]
    expiration: datetime
    created_at: datetime = field(default_factory=partial(datetime.now, timezone.utc))
    id: UUID = field(default_factory=uuid4)
    metadata: T | None = None


class LeaseStorage(Protocol[T]):
    async def create_lease(
        self, resource_ids: list[UUID], ttl: timedelta, metadata: T | None = None
    ) -> ResourceLease[T]:
        """
        Create a new resource lease.

        Args:
            resource_ids: The IDs of the resources that the lease is associated with.
            ttl: How long the lease should initially be held for.
            metadata: Additional metadata associated with the lease.

        Returns:
            A ResourceLease object representing the lease.
        """
        ...

    async def read_lease(self, lease_id: UUID) -> ResourceLease[T] | None:
        """
        Read a resource lease.

        Args:
            lease_id: The ID of the lease to read.

        Returns:
            A ResourceLease object representing the lease, or None if not found.
        """
        ...

    async def renew_lease(self, lease_id: UUID, ttl: timedelta) -> None:
        """
        Renew a resource lease.

        Args:
            lease_id: The ID of the lease to renew.
            ttl: The new amount of time the lease should be held for.
        """
        ...

    async def revoke_lease(self, lease_id: UUID) -> None:
        """
        Release a resource lease by removing it from list of active leases.

        Args:
            lease_id: The ID of the lease to release.
        """
        ...


# Prefect-specific helper utilities for working with concurrency leases.
# These functions centralize normalization/fallback logic so API layers stay thin.

from typing import TYPE_CHECKING, Any  # noqa: E402

from prefect.server.database import PrefectDBInterface  # noqa: E402
from prefect.server.models import (  # noqa: E402
    concurrency_limits_v2 as cl_v2_models,
)

if TYPE_CHECKING:  # pragma: no cover
    from prefect.server.concurrency.lease_storage import ConcurrencyLeaseStorage


async def get_active_slots_from_leases(
    limit_id: UUID, lease_storage: "ConcurrencyLeaseStorage | None" = None
) -> list[str]:
    """Extract task_run IDs from active leases for a given limit.

    Handles backends that provide a holder listing helper and those that do not by
    falling back to scanning active leases.
    """
    if lease_storage is None:
        # Local import to avoid circular dependency during module import
        from prefect.server.concurrency.lease_storage import (
            get_concurrency_lease_storage,
        )

        lease_storage = get_concurrency_lease_storage()
    active_holders: list[str] = []

    # Prefer storage-provided enumeration when available
    list_fn = getattr(lease_storage, "list_holders_for_limit", None)
    holders: list[Any] = []
    if callable(list_fn):
        holders = await list_fn(limit_id)  # type: ignore[misc]
    # If storage does not support holder listing or returned nothing, scan leases
    if not holders:
        for lid in await lease_storage.read_active_lease_ids(limit=1024):
            lease = await lease_storage.read_lease(lid)
            if not lease or limit_id not in lease.resource_ids:
                continue
            if lease.metadata and getattr(lease.metadata, "holder", None):
                holder_obj = lease.metadata.holder
                if isinstance(holder_obj, dict):
                    holders.append(holder_obj)
                else:
                    # Try to normalize pydantic model or typed object
                    dumped = None
                    if hasattr(holder_obj, "model_dump"):
                        try:
                            dumped = holder_obj.model_dump()  # type: ignore[attr-defined]
                        except Exception:
                            dumped = None
                    if isinstance(dumped, dict):
                        holders.append(dumped)
                    else:
                        htype = getattr(holder_obj, "type", None)
                        hid = getattr(holder_obj, "id", None)
                        if htype and hid:
                            holders.append({"type": str(htype), "id": str(hid)})

    # holders may be provided by storage helper or reconstructed by scanning leases
    for holder in holders:
        # Support shapes:
        # 1) {"type": "task_run", "id": "..."}
        # 2) {"holder": {"type": "task_run", "id": "..."}, "slots": N}
        # 3) typed objects with attribute `.holder` or attributes `.type`/`.id`
        h: object
        if isinstance(holder, dict):
            h = holder.get("holder") if "holder" in holder else holder
        else:
            h = getattr(holder, "holder", holder)

        if isinstance(h, dict):
            if h.get("type") == "task_run" and h.get("id"):
                active_holders.append(str(h["id"]))
        else:
            htype = getattr(h, "type", None)
            hid = getattr(h, "id", None)
            if htype == "task_run" and hid:
                active_holders.append(str(hid))

    # Deduplicate
    return list(dict.fromkeys(active_holders))


async def find_lease_for_task_run(
    task_run_id: UUID,
    tags: list[str],
    db: PrefectDBInterface,
    lease_storage: "ConcurrencyLeaseStorage | None" = None,
) -> UUID | None:
    """Find the lease ID for a given task run across tag-based limits.

    Attempts to use a backend helper if available; otherwise scans active leases.
    """
    if lease_storage is None:
        # Local import to avoid circular dependency during module import
        from prefect.server.concurrency.lease_storage import (
            get_concurrency_lease_storage,
        )

        lease_storage = get_concurrency_lease_storage()

    # Convert tags to V2 names to check relevant limits
    v2_names = [f"tag:{tag}" for tag in tags]

    async with db.session_context() as session:
        limit_ids: list[UUID] = []
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

    async def read_expired_lease_ids(self, limit: int = 100) -> list[UUID]:
        """
        Read the IDs of expired leases.

        Args:
            limit: The maximum number of expired leases to read.

        Returns:
            A list of UUIDs representing the expired leases.
        """
        ...
