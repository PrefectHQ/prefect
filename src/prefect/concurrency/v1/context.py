from contextvars import ContextVar
from typing import Any, ClassVar
from uuid import UUID

from typing_extensions import Self

from prefect.client.orchestration import get_client
from prefect.context import ContextModel, Field


class ConcurrencyContext(ContextModel):
    __var__: ClassVar[ContextVar[Self]] = ContextVar("concurrency_v1")

    # Track the limits that have been acquired but were not able to be released
    # due to cancellation or some other error. These limits are released when
    # the context manager exits.
    cleanup_slots: list[tuple[list[str], float, UUID]] = Field(default_factory=list)

    def __exit__(self, *exc_info: Any) -> None:
        if self.cleanup_slots:
            with get_client(sync_client=True) as client:
                for names, occupancy_seconds, task_run_id in self.cleanup_slots:
                    client.decrement_v1_concurrency_slots(
                        names=names,
                        occupancy_seconds=occupancy_seconds,
                        task_run_id=task_run_id,
                    )

        return super().__exit__(*exc_info)
