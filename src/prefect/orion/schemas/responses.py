import datetime
from typing import Dict
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


class HistoryResponse(PrefectBaseModel):
    interval_start: datetime.datetime
    interval_end: datetime.datetime
    states: Dict[schemas.states.StateType, int]


class StateAbortDetails(PrefectBaseModel):
    reason: str = None
