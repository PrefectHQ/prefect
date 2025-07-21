from contextvars import ContextVar
from typing import Any, ClassVar
from uuid import UUID

from typing_extensions import Self

from prefect.client.orchestration import get_client
from prefect.context import ContextModel, Field


class ConcurrencyContext(ContextModel):
    __var__: ClassVar[ContextVar[Self]] = ContextVar("concurrency")

    # Track the leases that have been acquired but were not able to be released
    # due to cancellation or some other error. These leases are revoked when
    # the context manager exits.
    cleanup_lease_ids: list[UUID] = Field(default_factory=lambda: [])

    def __exit__(self, *exc_info: Any) -> None:
        if self.cleanup_lease_ids:
            with get_client(sync_client=True) as client:
                for lease_id in self.cleanup_lease_ids:
                    client.release_concurrency_slots_with_lease(lease_id=lease_id)

        return super().__exit__(*exc_info)
