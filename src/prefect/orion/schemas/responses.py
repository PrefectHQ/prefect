from prefect.orion.utilities.enum import AutoEnum
from prefect.orion.utilities.schemas import PrefectBaseModel


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


class StateAbortDetails(PrefectBaseModel):
    reason: str = None
