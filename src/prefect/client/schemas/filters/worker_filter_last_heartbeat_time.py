from typing import Optional

from pydantic import Field
from pydantic_extra_types.pendulum_dt import DateTime

from prefect._internal.schemas.bases import PrefectBaseModel


class WorkerFilterLastHeartbeatTime(PrefectBaseModel):
    """Filter by `Worker.last_heartbeat_time`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description=(
            "Only include processes whose last heartbeat was at or before this time"
        ),
    )
    after_: Optional[DateTime] = Field(
        default=None,
        description=(
            "Only include processes whose last heartbeat was at or after this time"
        ),
    )