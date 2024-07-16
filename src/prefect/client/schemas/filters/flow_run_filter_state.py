from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .flow_run_filter_state_name import FlowRunFilterStateName
from .flow_run_filter_state_type import FlowRunFilterStateType
from .operator_mixin import OperatorMixin


class FlowRunFilterState(PrefectBaseModel, OperatorMixin):
    type: Optional[FlowRunFilterStateType] = Field(
        default=None, description="Filter criteria for `FlowRun` state type"
    )
    name: Optional[FlowRunFilterStateName] = Field(
        default=None, description="Filter criteria for `FlowRun` state name"
    )