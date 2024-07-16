from typing import Optional
from uuid import UUID

from pydantic import Field
from pydantic_extra_types.pendulum_dt import DateTime

from prefect._internal.schemas.bases import ActionBaseModel


class LogCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a log."""

    name: str = Field(default=..., description="The logger name.")
    level: int = Field(default=..., description="The log level.")
    message: str = Field(default=..., description="The log message.")
    timestamp: DateTime = Field(default=..., description="The log timestamp.")
    flow_run_id: Optional[UUID] = Field(None)
    task_run_id: Optional[UUID] = Field(None)