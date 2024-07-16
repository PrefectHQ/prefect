from typing import Optional

from pydantic import Field, field_validator

from prefect._internal.schemas.bases import ActionBaseModel
from prefect._internal.schemas.validators import (
    validate_schedule_max_scheduled_runs,
)
from prefect.client.schemas.schedules import SCHEDULE_TYPES
from prefect.settings import PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS
from prefect.types import (
    PositiveInteger,
)


class DeploymentScheduleUpdate(ActionBaseModel):
    schedule: Optional[SCHEDULE_TYPES] = Field(
        default=None, description="The schedule for the deployment."
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

    catchup: Optional[bool] = Field(
        default=None,
        description="Whether or not a worker should catch up on Late runs for the schedule.",
    )

    @field_validator("max_scheduled_runs")
    @classmethod
    def validate_max_scheduled_runs(cls, v):
        return validate_schedule_max_scheduled_runs(
            v, PREFECT_DEPLOYMENT_SCHEDULE_MAX_SCHEDULED_RUNS.value()
        )