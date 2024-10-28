from contextvars import ContextVar
from typing import List, Tuple
from uuid import UUID

from prefect.client.orchestration import get_client
from prefect.context import ContextModel, Field


class ConcurrencyContext(ContextModel):
    __var__: ContextVar = ContextVar("concurrency_v1")

    # Track the limits that have been acquired but were not able to be released
    # due to cancellation or some other error. These limits are released when
    # the context manager exits.
    cleanup_slots: List[Tuple[List[str], float, UUID]] = Field(default_factory=list)

    def __exit__(self, *exc_info):
        if self.cleanup_slots:
            with get_client(sync_client=True) as client:
                for names, occupancy_seconds, task_run_id in self.cleanup_slots:
                    client.decrement_v1_concurrency_slots(
                        names=names,
                        occupancy_seconds=occupancy_seconds,
                        task_run_id=task_run_id,
                    )

        return super().__exit__(*exc_info)
