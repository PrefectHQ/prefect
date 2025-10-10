from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypedDict
from uuid import UUID

import anyio

from prefect.server.concurrency.lease_storage import (
    ConcurrencyLeaseHolder,
    ConcurrencyLimitLeaseMetadata,
)
from prefect.server.concurrency.lease_storage import (
    ConcurrencyLeaseStorage as _ConcurrencyLeaseStorage,
)
from prefect.server.utilities.leasing import ResourceLease
from prefect.settings.context import get_current_settings


class _LeaseFile(TypedDict):
    id: str
    resource_ids: list[str]
    metadata: dict[str, Any] | None
    expiration: str
    created_at: str


class ConcurrencyLeaseStorage(_ConcurrencyLeaseStorage):
    """
    A file-based concurrency lease storage implementation that stores leases on disk.
    """

    def __init__(self, storage_path: Path | None = None):
        prefect_home = get_current_settings().home
        self.storage_path: Path = Path(
            storage_path or prefect_home / "concurrency_leases"
        )

    def _ensure_storage_path(self) -> None:
        """Ensure the storage path exists, creating it if necessary."""
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _lease_file_path(self, lease_id: UUID) -> Path:
        return self.storage_path / f"{lease_id}.json"

    def _expiration_index_path(self) -> anyio.Path:
        return anyio.Path(self.storage_path / "expirations.json")

    async def _load_expiration_index(self) -> dict[str, str]:
        """Load the expiration index from disk."""
        expiration_file = self._expiration_index_path()
        if not await expiration_file.exists():
            return {}

        try:
            return json.loads(await expiration_file.read_text())
        except (json.JSONDecodeError, KeyError, ValueError):
            return {}

    def _save_expiration_index(self, index: dict[str, str]) -> None:
        """Save the expiration index to disk."""
        self._ensure_storage_path()
        expiration_file = self._expiration_index_path()

        with open(expiration_file, "w") as f:
            json.dump(index, f)

    async def _update_expiration_index(
        self, lease_id: UUID, expiration: datetime
    ) -> None:
        """Update a single lease's expiration in the index."""
        index = await self._load_expiration_index()
        index[str(lease_id)] = expiration.isoformat()
        self._save_expiration_index(index)

    async def _remove_from_expiration_index(self, lease_id: UUID) -> None:
        """Remove a lease from the expiration index."""
        index = await self._load_expiration_index()
        index.pop(str(lease_id), None)
        self._save_expiration_index(index)

    def _serialize_lease(
        self, lease: ResourceLease[ConcurrencyLimitLeaseMetadata]
    ) -> _LeaseFile:
        metadata_dict: dict[str, Any] | None = None
        if lease.metadata:
            metadata_dict = {"slots": lease.metadata.slots}
            if lease.metadata.holder is not None:
                metadata_dict["holder"] = lease.metadata.holder.model_dump(mode="json")

        return {
            "id": str(lease.id),
            "resource_ids": [str(rid) for rid in lease.resource_ids],
            "metadata": metadata_dict,
            "expiration": lease.expiration.isoformat(),
            "created_at": lease.created_at.isoformat(),
        }

    def _deserialize_lease(
        self, data: _LeaseFile
    ) -> ResourceLease[ConcurrencyLimitLeaseMetadata]:
        lease_id = UUID(data["id"])
        resource_ids = [UUID(rid) for rid in data["resource_ids"]]
        metadata = None
        if data["metadata"]:
            metadata = ConcurrencyLimitLeaseMetadata(
                slots=data["metadata"]["slots"], holder=data["metadata"].get("holder")
            )
        expiration = datetime.fromisoformat(data["expiration"])
        created_at = datetime.fromisoformat(data["created_at"])
        lease = ResourceLease(
            id=lease_id,
            resource_ids=resource_ids,
            metadata=metadata,
            expiration=expiration,
            created_at=created_at,
        )
        return lease

    async def create_lease(
        self,
        resource_ids: list[UUID],
        ttl: timedelta,
        metadata: ConcurrencyLimitLeaseMetadata | None = None,
    ) -> ResourceLease[ConcurrencyLimitLeaseMetadata]:
        expiration = datetime.now(timezone.utc) + ttl
        lease = ResourceLease(
            resource_ids=resource_ids, metadata=metadata, expiration=expiration
        )

        self._ensure_storage_path()
        lease_file = self._lease_file_path(lease.id)
        lease_data = self._serialize_lease(lease)

        with open(lease_file, "w") as f:
            json.dump(lease_data, f)

        # Update expiration index
        await self._update_expiration_index(lease.id, expiration)

        return lease

    async def read_lease(
        self, lease_id: UUID
    ) -> ResourceLease[ConcurrencyLimitLeaseMetadata] | None:
        lease_file = self._lease_file_path(lease_id)

        if not lease_file.exists():
            return None

        try:
            with open(lease_file, "r") as f:
                lease_data = json.load(f)

            lease = self._deserialize_lease(lease_data)

            return lease
        except (json.JSONDecodeError, KeyError, ValueError):
            # Clean up corrupted lease file
            lease_file.unlink(missing_ok=True)
            await self._remove_from_expiration_index(lease_id)
            return None

    async def renew_lease(self, lease_id: UUID, ttl: timedelta) -> None:
        lease_file = self._lease_file_path(lease_id)

        if not lease_file.exists():
            return

        try:
            with open(lease_file, "r") as f:
                lease_data = json.load(f)

            # Update expiration time
            new_expiration = datetime.now(timezone.utc) + ttl
            lease_data["expiration"] = new_expiration.isoformat()

            self._ensure_storage_path()
            with open(lease_file, "w") as f:
                json.dump(lease_data, f)

            # Update expiration index
            await self._update_expiration_index(lease_id, new_expiration)
        except (json.JSONDecodeError, KeyError, ValueError):
            # Clean up corrupted lease file
            lease_file.unlink(missing_ok=True)
            await self._remove_from_expiration_index(lease_id)

    async def revoke_lease(self, lease_id: UUID) -> None:
        lease_file = self._lease_file_path(lease_id)
        lease_file.unlink(missing_ok=True)

        # Remove from expiration index
        await self._remove_from_expiration_index(lease_id)

    async def read_active_lease_ids(
        self, limit: int = 100, offset: int = 0
    ) -> list[UUID]:
        now = datetime.now(timezone.utc)

        expiration_index = await self._load_expiration_index()

        # Collect all active leases first
        all_active: list[UUID] = []
        for lease_id_str, expiration_str in expiration_index.items():
            try:
                lease_id = UUID(lease_id_str)
                expiration = datetime.fromisoformat(expiration_str)

                if expiration > now:
                    all_active.append(lease_id)
            except (ValueError, TypeError):
                continue

        # Apply offset and limit
        return all_active[offset : offset + limit]

    async def read_expired_lease_ids(self, limit: int = 100) -> list[UUID]:
        expired_leases: list[UUID] = []
        now = datetime.now(timezone.utc)

        expiration_index = await self._load_expiration_index()

        for lease_id_str, expiration_str in expiration_index.items():
            if len(expired_leases) >= limit:
                break

            try:
                lease_id = UUID(lease_id_str)
                expiration = datetime.fromisoformat(expiration_str)

                if expiration < now:
                    expired_leases.append(lease_id)
            except (ValueError, TypeError):
                continue

        return expired_leases

    async def list_holders_for_limit(
        self, limit_id: UUID
    ) -> list[tuple[UUID, ConcurrencyLeaseHolder]]:
        """List all holders for a given concurrency limit."""
        now = datetime.now(timezone.utc)
        holders_with_leases: list[tuple[UUID, ConcurrencyLeaseHolder]] = []

        # Get all active lease IDs - need to paginate through all
        all_active_lease_ids: list[UUID] = []
        offset = 0
        batch_size = 100
        while True:
            batch = await self.read_active_lease_ids(limit=batch_size, offset=offset)
            if not batch:
                break
            all_active_lease_ids.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size

        active_lease_ids = all_active_lease_ids

        for lease_id in active_lease_ids:
            lease = await self.read_lease(lease_id)
            if (
                lease
                and limit_id in lease.resource_ids
                and lease.expiration > now
                and lease.metadata
                and lease.metadata.holder
            ):
                holders_with_leases.append((lease.id, lease.metadata.holder))

        return holders_with_leases
