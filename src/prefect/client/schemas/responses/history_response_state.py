import datetime

from pydantic import Field

import prefect.client.schemas.objects as objects
from prefect._internal.schemas.bases import PrefectBaseModel


class HistoryResponseState(PrefectBaseModel):
    """Represents a single state's history over an interval."""

    state_type: objects.StateType = Field(default=..., description="The state type.")
    state_name: str = Field(default=..., description="The state name.")
    count_runs: int = Field(
        default=...,
        description="The number of runs in the specified state during the interval.",
    )
    sum_estimated_run_time: datetime.timedelta = Field(
        default=...,
        description="The total estimated run time of all runs during the interval.",
    )
    sum_estimated_lateness: datetime.timedelta = Field(
        default=...,
        description=(
            "The sum of differences between actual and expected start time during the"
            " interval."
        ),
    )
