"""
Schemas for special responses from the Orion API.
"""

import datetime
from typing import List

from pydantic import Field
from typing_extensions import Literal

import prefect.orion.schemas as schemas
from prefect.orion.utilities.schemas import PrefectBaseModel
from prefect.utilities.collections import AutoEnum


class SetStateStatus(AutoEnum):
    """Enumerates return statuses for setting run states."""

    ACCEPT = AutoEnum.auto()
    REJECT = AutoEnum.auto()
    ABORT = AutoEnum.auto()
    WAIT = AutoEnum.auto()


class StateAcceptDetails(PrefectBaseModel):
    """Details associated with an ACCEPT state transition."""

    type: Literal["accept_details"] = Field(
        "accept_details",
        description="The type of state transition detail. Used to ensure pydantic does not coerce into a different type.",
    )


class StateRejectDetails(PrefectBaseModel):
    """Details associated with a REJECT state transition."""

    type: Literal["reject_details"] = Field(
        "reject_details",
        description="The type of state transition detail. Used to ensure pydantic does not coerce into a different type.",
    )
    reason: str = Field(
        None, description="The reason why the state transition was rejected."
    )


class StateAbortDetails(PrefectBaseModel):
    """Details associated with an ABORT state transition."""

    type: Literal["abort_details"] = Field(
        "abort_details",
        description="The type of state transition detail. Used to ensure pydantic does not coerce into a different type.",
    )
    reason: str = Field(
        None, description="The reason why the state transition was aborted."
    )


class StateWaitDetails(PrefectBaseModel):
    """Details associated with a WAIT state transition."""

    type: Literal["wait_details"] = Field(
        "wait_details",
        description="The type of state transition detail. Used to ensure pydantic does not coerce into a different type.",
    )
    delay_seconds: int = Field(
        ...,
        description="The length of time in seconds the client should wait before transitioning states.",
    )
    reason: str = Field(
        None, description="The reason why the state transition should wait."
    )


class HistoryResponseState(PrefectBaseModel):
    """Represents a single state's history over an interval."""

    state_type: schemas.states.StateType = Field(..., description="The state type.")
    state_name: str = Field(..., description="The state name.")
    count_runs: int = Field(
        ...,
        description="The number of runs in the specified state during the interval.",
    )
    sum_estimated_run_time: datetime.timedelta = Field(
        ..., description="The total estimated run time of all runs during the interval."
    )
    sum_estimated_lateness: datetime.timedelta = Field(
        ...,
        description="The sum of differences between actual and expected start time during the interval.",
    )


class HistoryResponse(PrefectBaseModel):
    """Represents a history of aggregation states over an interval"""

    interval_start: datetime.datetime = Field(
        ..., description="The start date of the interval."
    )
    interval_end: datetime.datetime = Field(
        ..., description="The end date of the interval."
    )
    states: List[HistoryResponseState] = Field(
        ..., description="A list of state histories during the interval."
    )
