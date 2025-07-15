from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from prefect.server.concurrency.lease_storage import (
    ConcurrencyLeaseStorage as _ConcurrencyLeaseStorage,
)
from prefect.server.concurrency.lease_storage import (
    ConcurrencyLimitLeaseMetadata,
)
from prefect.server.utilities.leasing import ResourceLease
from prefect.settings.context import get_current_settings


class ConcurrencyLeaseStorage(_ConcurrencyLeaseStorage):
    """
    A file-based concurrency lease storage implementation that stores leases on disk.
    """

    def __init__(self, storage_path: Path | None = None):
        prefect_home = get_current_settings().home
        self.storage_path = Path(storage_path or prefect_home / "concurrency_leases")

    def _ensure_storage_path(self) -> None:
        """Ensure the storage path exists, creating it if necessary."""
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _lease_file_path(self, lease_id: UUID) -> Path:
        return self.storage_path / f"{lease_id}.json"

    def _serialize_lease(
        self, lease: ResourceLease[ConcurrencyLimitLeaseMetadata], expiration: datetime
    ) -> dict:
        return {
            "resource_ids": [str(rid) for rid in lease.resource_ids],
            "metadata": {"slots": lease.metadata.slots} if lease.metadata else None,
            "expiration": expiration.isoformat(),
        }

    def _deserialize_lease(
        self, data: dict
    ) -> ResourceLease[ConcurrencyLimitLeaseMetadata]:
        resource_ids = [UUID(rid) for rid in data["resource_ids"]]
        metadata = (
            ConcurrencyLimitLeaseMetadata(slots=data["metadata"]["slots"])
            if data["metadata"]
            else None
        )
        expiration = datetime.fromisoformat(data["expiration"])
        lease = ResourceLease(
            resource_ids=resource_ids, metadata=metadata, expiration=expiration
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
        lease_data = self._serialize_lease(lease, expiration)

        with open(lease_file, "w") as f:
            json.dump(lease_data, f)

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

            # Check if lease is expired
            if lease.expiration < datetime.now(timezone.utc):
                # Clean up expired lease
                lease_file.unlink(missing_ok=True)
                return None

            return lease
        except (json.JSONDecodeError, KeyError, ValueError):
            # Clean up corrupted lease file
            lease_file.unlink(missing_ok=True)
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
        except (json.JSONDecodeError, KeyError, ValueError):
            # Clean up corrupted lease file
            lease_file.unlink(missing_ok=True)

    async def release_lease(self, lease_id: UUID) -> None:
        lease_file = self._lease_file_path(lease_id)
        lease_file.unlink(missing_ok=True)

    async def read_expired_lease_ids(self, limit: int = 100) -> list[UUID]:
        expired_leases = []
        now = datetime.now(timezone.utc)

        for lease_file in self.storage_path.glob("*.json"):
            if len(expired_leases) >= limit:
                break

            try:
                lease_id = UUID(lease_file.stem)

                with open(lease_file, "r") as f:
                    lease_data = json.load(f)

                expiration = datetime.fromisoformat(lease_data["expiration"])

                if expiration < now:
                    expired_leases.append(lease_id)
            except (json.JSONDecodeError, KeyError, ValueError):
                # Clean up corrupted lease file
                lease_file.unlink(missing_ok=True)

        return expired_leases
