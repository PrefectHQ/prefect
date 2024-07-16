from typing import (
    Optional,
)
from uuid import UUID

from pydantic import (
    Field,
)

from prefect._internal.schemas.bases import ObjectBaseModel
from prefect.client.schemas.schedules import SCHEDULE_TYPES
from prefect.types import (
    PositiveInteger,
)


class DeploymentSchedule(ObjectBaseModel):
    deployment_id: Optional[UUID] = Field(
        default=None,
        description="The deployment id associated with this schedule.",
    )
    schedule: SCHEDULE_TYPES = Field(
        default=..., description="The schedule for the deployment."
    )
    active: bool = Field(
        default=True, description="Whether or not the schedule is active."
    )
    max_active_runs: Optional[PositiveInteger] = Field(
        default=None,
        description="The maximum number of active runs for the schedule.",
    )
    max_scheduled_runs: Optional[PositiveInteger] = Field(
        default=None,
        description="The maximum number of scheduled runs for the schedule.",
    )
    catchup: bool = Field(
        default=False,
        description="Whether or not a worker should catch up on Late runs for the schedule.",
    )
