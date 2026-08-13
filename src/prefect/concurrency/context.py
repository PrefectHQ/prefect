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
    __var__: ClassVar[ContextVar[Self]] = ContextVar("concurrency")

    # Track the leases that have been acquired but were not able to be released
    # due to cancellation or some other error. These leases are revoked when
    # the context manager exits.
    cleanup_lease_ids: list[UUID] = Field(default_factory=lambda: [])

    def __exit__(self, *exc_info: Any) -> None:
        # Releasing these leases is best-effort: a failure for one lease must not
        # strand the others or skip the context teardown below.
        if self.cleanup_lease_ids:
            logger = _cleanup_logger()
            try:
                with get_client(sync_client=True) as client:
                    for lease_id in self.cleanup_lease_ids:
                        try:
                            client.release_concurrency_slots_with_lease(
                                lease_id=lease_id
                            )
                        except Exception:
                            logger.warning(
                                "Failed to release concurrency lease %s during cleanup",
                                lease_id,
                                exc_info=True,
                            )
            except Exception:
                logger.warning(
                    "Failed to release concurrency leases during cleanup",
                    exc_info=True,
                )

        return super().__exit__(*exc_info)
