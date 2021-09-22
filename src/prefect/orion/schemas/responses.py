import datetime
from typing import List
from prefect.utilities.compat import Literal
from prefect.orion.utilities.enum import AutoEnum
from prefect.orion.utilities.schemas import PrefectBaseModel
from prefect.orion import schemas


class SetStateStatus(AutoEnum):
    ACCEPT = AutoEnum.auto()
    REJECT = AutoEnum.auto()
    ABORT = AutoEnum.auto()
    WAIT = AutoEnum.auto()


class StateAcceptDetails(PrefectBaseModel):
    type: Literal["accept_details"] = "accept_details"


class StateRejectDetails(PrefectBaseModel):
    type: Literal["reject_details"] = "reject_details"
    reason: str = None


class StateAbortDetails(PrefectBaseModel):
    type: Literal["abort_details"] = "abort_details"
    reason: str = None


class StateWaitDetails(PrefectBaseModel):
    type: Literal["wait_details"] = "wait_details"
    delay_seconds: int
    reason: str = None


class HistoryResponseState(PrefectBaseModel):
    name: str
    type: schemas.states.StateType
    count: int


class HistoryResponse(PrefectBaseModel):
    interval_start: datetime.datetime
    interval_end: datetime.datetime
    states: List[HistoryResponseState]
