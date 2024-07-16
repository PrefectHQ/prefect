from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class DeploymentFilterIsScheduleActive(PrefectBaseModel):
    """Filter by `Deployment.is_schedule_active`."""

    eq_: Optional[bool] = Field(
        default=None,
        description="Only returns where deployment schedule is/is not active",
    )