import logging
from contextvars import ContextVar
from typing import Any, ClassVar
from uuid import UUID

from typing_extensions import Self

from prefect.client.orchestration import get_client
from prefect.context import ContextModel, Field
from prefect.logging.loggers import get_logger, get_run_logger


def _cleanup_logger() -> "logging.Logger | logging.LoggerAdapter[logging.Logger]":
    try:
        # Use a run logger if available so failures reach the run logs
        return get_run_logger()
    except Exception:
        return get_logger("concurrency")


class ConcurrencyContext(ContextModel):
    __var__: ClassVar[ContextVar[Self]] = ContextVar("concurrency_v1")

    # Track the limits that have been acquired but were not able to be released
    # due to cancellation or some other error. These limits are released when
    # the context manager exits.
    cleanup_slots: list[tuple[list[str], float, UUID]] = Field(default_factory=list)

    def __exit__(self, *exc_info: Any) -> None:
        # Releasing these slots is best-effort: a failure for one entry must not
        # strand the others or skip the context teardown below.
        if self.cleanup_slots:
            logger = _cleanup_logger()
            try:
                with get_client(sync_client=True) as client:
                    for names, occupancy_seconds, task_run_id in self.cleanup_slots:
                        try:
                            client.decrement_v1_concurrency_slots(
                                names=names,
                                occupancy_seconds=occupancy_seconds,
                                task_run_id=task_run_id,
                            )
                        except Exception:
                            logger.warning(
                                "Failed to release concurrency slots %s for task run %s during cleanup",
                                names,
                                task_run_id,
                                exc_info=True,
                            )
            except Exception:
                logger.warning(
                    "Failed to release concurrency slots during cleanup",
                    exc_info=True,
                )

        return super().__exit__(*exc_info)
