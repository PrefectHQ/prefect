from typing import (
    Optional,
)
from uuid import UUID

from pydantic import (
    Field,
)
from pydantic_extra_types.pendulum_dt import DateTime

from prefect._internal.schemas.bases import ObjectBaseModel


class Log(ObjectBaseModel):
    """An ORM representation of log data."""

    name: str = Field(default=..., description="The logger name.")
    level: int = Field(default=..., description="The log level.")
    message: str = Field(default=..., description="The log message.")
    timestamp: DateTime = Field(default=..., description="The log timestamp.")
    flow_run_id: Optional[UUID] = Field(
        default=None, description="The flow run ID associated with the log."
    )
    task_run_id: Optional[UUID] = Field(
        default=None, description="The task run ID associated with the log."
    )
