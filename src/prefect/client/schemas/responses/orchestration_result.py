from typing import Optional, Union

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.client.schemas.objects import State

from .set_state_status import SetStateStatus
from .state_abort_details import StateAbortDetails
from .state_accept_details import StateAcceptDetails
from .state_reject_details import StateRejectDetails
from .state_wait_details import StateWaitDetails

StateResponseDetails = Union[
    StateAcceptDetails, StateWaitDetails, StateRejectDetails, StateAbortDetails
]


class OrchestrationResult(PrefectBaseModel):
    """
    A container for the output of state orchestration.
    """

    state: Optional[State]
    status: SetStateStatus
    details: StateResponseDetails
