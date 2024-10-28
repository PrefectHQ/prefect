from contextvars import ContextVar
from typing import List, Tuple

from prefect.client.orchestration import get_client
from prefect.context import ContextModel, Field


class ConcurrencyContext(ContextModel):
    __var__: ContextVar = ContextVar("concurrency")

    # Track the slots that have been acquired but were not able to be released
    # due to cancellation or some other error. These slots are released when
    # the context manager exits.
    cleanup_slots: List[Tuple[List[str], int, float]] = Field(default_factory=list)

    def __exit__(self, *exc_info):
        if self.cleanup_slots:
            with get_client(sync_client=True) as client:
                for names, occupy, occupancy_seconds in self.cleanup_slots:
                    client.release_concurrency_slots(
                        names=names, slots=occupy, occupancy_seconds=occupancy_seconds
                    )

        return super().__exit__(*exc_info)
