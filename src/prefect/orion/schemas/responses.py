from typing import Union

from prefect.orion.schemas.states import State, RunDetails, StateDetails
from prefect.orion.utilities.enum import AutoEnum
from prefect.orion.utilities.schemas import PrefectBaseModel


class SetStateStatus(AutoEnum):
    ACCEPT = AutoEnum.auto()
    REJECT = AutoEnum.auto()
    ABORT = AutoEnum.auto()


class SetStateAcceptDetails(PrefectBaseModel):
    """When a state is accepted, the payload includes only updated details"""

    run_details: RunDetails = None
    state_details: StateDetails = None


class SetStateRejectDetails(PrefectBaseModel):
    """When a state is rejected, the payload includes a reason and a new state"""

    reason: str = None
    state: State = None


class SetStateResponse(PrefectBaseModel):
    status: SetStateStatus
    details: Union[SetStateAcceptDetails, SetStateRejectDetails]
