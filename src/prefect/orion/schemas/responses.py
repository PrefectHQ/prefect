from typing import Optional

from prefect.orion.schemas.states import State
from prefect.orion.utilities.enum import AutoEnum
from prefect.orion.utilities.schemas import PrefectBaseModel


class SetStateStatus(AutoEnum):
    ACCEPT = AutoEnum.auto()
    REJECT = AutoEnum.auto()
    ABORT = AutoEnum.auto()
    WAIT = AutoEnum.auto()


class SetStateResponse(PrefectBaseModel):
    state: Optional[State]
    status: SetStateStatus
