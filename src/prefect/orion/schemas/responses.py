"""
Schemas for special responses from the Orion API.
"""

import datetime
from typing import List
from typing_extensions import Literal
from prefect.orion.utilities.enum import AutoEnum
from prefect.orion.utilities.schemas import PrefectBaseModel
from prefect.orion import schemas


class SetStateStatus(AutoEnum):
    """Enumerates return statuses for setting run states."""

    ACCEPT = AutoEnum.auto()
    REJECT = AutoEnum.auto()
    ABORT = AutoEnum.auto()
    WAIT = AutoEnum.auto()


class StateAcceptDetails(PrefectBaseModel):
    """Details associated with an ACCEPT state transition."""

    type: Literal["accept_details"] = "accept_details"


class StateRejectDetails(PrefectBaseModel):
    """Details associated with a REJECT state transition."""

    type: Literal["reject_details"] = "reject_details"
    reason: str = None


class StateAbortDetails(PrefectBaseModel):
    """Details associated with an ABORT state transition."""

    type: Literal["abort_details"] = "abort_details"
    reason: str = None


class StateWaitDetails(PrefectBaseModel):
    """Details associated with a WAIT state transition."""

    type: Literal["wait_details"] = "wait_details"
    delay_seconds: int
    reason: str = None


class HistoryResponseState(PrefectBaseModel):
    """Represents a single state's history over an interval."""

    state_type: schemas.states.StateType
    state_name: str
    count_runs: int
    sum_estimated_run_time: datetime.timedelta
    sum_estimated_lateness: datetime.timedelta


class HistoryResponse(PrefectBaseModel):
    """Represents a history of aggregation states over an interval"""

    interval_start: datetime.datetime
    interval_end: datetime.datetime
    states: List[HistoryResponseState]
