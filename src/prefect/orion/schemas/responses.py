import datetime
from typing import List
from prefect.orion.utilities.enum import AutoEnum
from prefect.orion.utilities.schemas import PrefectBaseModel
from prefect.orion import schemas


class SetStateStatus(AutoEnum):
    ACCEPT = AutoEnum.auto()
    REJECT = AutoEnum.auto()
    ABORT = AutoEnum.auto()
    WAIT = AutoEnum.auto()


class StateAcceptDetails(PrefectBaseModel):
    class Config:
        extra = "forbid"

    pass


class StateRejectDetails(PrefectBaseModel):
    class Config:
        extra = "forbid"

    reason: str = None


class StateAbortDetails(PrefectBaseModel):
    class Config:
        extra = "forbid"

    reason: str = None


class StateWaitDetails(PrefectBaseModel):
    class Config:
        extra = "forbid"

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
