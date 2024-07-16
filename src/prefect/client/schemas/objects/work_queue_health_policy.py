from typing import (
    Optional,
)

import pendulum
from pydantic import (
    Field,
)
from pydantic_extra_types.pendulum_dt import DateTime

from prefect._internal.schemas.bases import PrefectBaseModel


class WorkQueueHealthPolicy(PrefectBaseModel):
    maximum_late_runs: Optional[int] = Field(
        default=0,
        description=(
            "The maximum number of late runs in the work queue before it is deemed"
            " unhealthy. Defaults to `0`."
        ),
    )
    maximum_seconds_since_last_polled: Optional[int] = Field(
        default=60,
        description=(
            "The maximum number of time in seconds elapsed since work queue has been"
            " polled before it is deemed unhealthy. Defaults to `60`."
        ),
    )

    def evaluate_health_status(
        self, late_runs_count: int, last_polled: Optional[DateTime] = None
    ) -> bool:
        """
        Given empirical information about the state of the work queue, evaluate its health status.

        Args:
            late_runs: the count of late runs for the work queue.
            last_polled: the last time the work queue was polled, if available.

        Returns:
            bool: whether or not the work queue is healthy.
        """
        healthy = True
        if (
            self.maximum_late_runs is not None
            and late_runs_count > self.maximum_late_runs
        ):
            healthy = False

        if self.maximum_seconds_since_last_polled is not None:
            if (
                last_polled is None
                or pendulum.now("UTC").diff(last_polled).in_seconds()
                > self.maximum_seconds_since_last_polled
            ):
                healthy = False

        return healthy