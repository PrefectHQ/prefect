from contextvars import ContextVar
from typing import Any, ClassVar

from typing_extensions import Self

from prefect.client.orchestration import get_client
from prefect.context import ContextModel, Field


class ConcurrencyContext(ContextModel):
    __var__: ClassVar[ContextVar[Self]] = ContextVar("concurrency")

    # Track the slots that have been acquired but were not able to be released
    # due to cancellation or some other error. These slots are released when
    # the context manager exits.
    cleanup_slots: list[tuple[list[str], int, float]] = Field(
        default_factory=lambda: []
    )

    def __exit__(self, *exc_info: Any) -> None:
        if self.cleanup_slots:
            with get_client(sync_client=True) as client:
                for names, occupy, occupancy_seconds in self.cleanup_slots:
                    client.release_concurrency_slots(
                        names=names, slots=occupy, occupancy_seconds=occupancy_seconds
                    )

        return super().__exit__(*exc_info)
