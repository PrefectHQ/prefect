from typing import (
    Optional,
)
from uuid import UUID

from pydantic import (
    Field,
)
from pydantic_extra_types.pendulum_dt import DateTime

from prefect._internal.schemas.bases import ObjectBaseModel
from prefect.utilities.names import generate_slug


class Agent(ObjectBaseModel):
    """An ORM representation of an agent"""

    name: str = Field(
        default_factory=lambda: generate_slug(2),
        description=(
            "The name of the agent. If a name is not provided, it will be"
            " auto-generated."
        ),
    )
    work_queue_id: UUID = Field(
        default=..., description="The work queue with which the agent is associated."
    )
    last_activity_time: Optional[DateTime] = Field(
        default=None, description="The last time this agent polled for work."
    )