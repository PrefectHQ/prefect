from typing import List

from pydantic import Field
from pydantic_extra_types.pendulum_dt import DateTime

from prefect._internal.schemas.bases import PrefectBaseModel

from .history_response_state import HistoryResponseState


class HistoryResponse(PrefectBaseModel):
    """Represents a history of aggregation states over an interval"""

    interval_start: DateTime = Field(
        default=..., description="The start date of the interval."
    )
    interval_end: DateTime = Field(
        default=..., description="The end date of the interval."
    )
    states: List[HistoryResponseState] = Field(
        default=..., description="A list of state histories during the interval."
    )
