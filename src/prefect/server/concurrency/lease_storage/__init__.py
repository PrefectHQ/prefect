from __future__ import annotations

from datetime import timedelta
import importlib
from typing import Any, ClassVar, Literal, Optional, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from prefect.server.utilities.leasing import LeaseStorage, ResourceLease
from prefect.settings.context import get_current_settings


@runtime_checkable
class ConcurrencyLeaseStorageModule(Protocol):
    ConcurrencyLeaseStorage: type[ConcurrencyLeaseStorage]


class ConcurrencyLeaseHolder(BaseModel):
    """Model for validating concurrency lease holder information."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    type: Literal["flow_run", "task_run", "deployment"]
    id: UUID


class ConcurrencyLimitLeaseMetadata(BaseModel):
    """Model for validating concurrency limit lease metadata."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    slots: int
    holder: Optional[ConcurrencyLeaseHolder] = None


class ConcurrencyLeaseStorage(LeaseStorage[ConcurrencyLimitLeaseMetadata]):
    async def create_lease(
        self,
        resource_ids: list[UUID],
        ttl: timedelta,
        metadata: ConcurrencyLimitLeaseMetadata | None = None,
    ) -> ResourceLease[ConcurrencyLimitLeaseMetadata]: ...

    async def read_lease(
        self, lease_id: UUID
    ) -> ResourceLease[ConcurrencyLimitLeaseMetadata] | None: ...

    async def renew_lease(self, lease_id: UUID, ttl: timedelta) -> None: ...

    async def revoke_lease(self, lease_id: UUID) -> None: ...

    async def read_active_lease_ids(self) -> list[UUID]: ...

    async def read_expired_lease_ids(self, limit: int = 100) -> list[UUID]: ...


def get_concurrency_lease_storage() -> ConcurrencyLeaseStorage:
    """
    Returns a ConcurrencyLeaseStorage instance based on the configured lease storage module.

    Will raise a ValueError if the configured module does not pass a type check.
    """
    concurrency_lease_storage_module = importlib.import_module(
        get_current_settings().server.concurrency.lease_storage
    )
    if not isinstance(concurrency_lease_storage_module, ConcurrencyLeaseStorageModule):
        raise ValueError(
            f"The module {get_current_settings().server.concurrency.lease_storage} does not contain a ConcurrencyLeaseStorage class"
        )
    return concurrency_lease_storage_module.ConcurrencyLeaseStorage()
