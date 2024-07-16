import datetime
from typing import (
    Optional,
)
from uuid import UUID

from pydantic import (
    Field,
)

from prefect._internal.schemas.bases import ObjectBaseModel

from .worker_status import WorkerStatus


class Worker(ObjectBaseModel):
    """An ORM representation of a worker"""

    name: str = Field(description="The name of the worker.")
    work_pool_id: UUID = Field(
        description="The work pool with which the queue is associated."
    )
    last_heartbeat_time: datetime.datetime = Field(
        None, description="The last time the worker process sent a heartbeat."
    )
    heartbeat_interval_seconds: Optional[int] = Field(
        default=None,
        description=(
            "The number of seconds to expect between heartbeats sent by the worker."
        ),
    )
    status: WorkerStatus = Field(
        WorkerStatus.OFFLINE,
        description="Current status of the worker.",
    )