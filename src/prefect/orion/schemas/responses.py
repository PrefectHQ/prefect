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
    pass


class StateRejectDetails(PrefectBaseModel):
    reason: str = None


class StateWaitDetails(PrefectBaseModel):
    delay_seconds: int
    reason: str = None


class HistoryResponseState(PrefectBaseModel):
    state_type: schemas.states.StateType
    state_name: str
    count_runs: int
    sum_estimated_run_time: datetime.timedelta
    sum_estimated_lateness: datetime.timedelta


class HistoryResponse(PrefectBaseModel):
    interval_start: datetime.datetime
    interval_end: datetime.datetime
    states: List[HistoryResponseState]


class StateAbortDetails(PrefectBaseModel):
    reason: str = None
