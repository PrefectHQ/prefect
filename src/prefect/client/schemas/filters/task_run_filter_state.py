from typing import Optional

from prefect._internal.schemas.bases import PrefectBaseModel

from .operator_mixin import OperatorMixin
from .task_run_filter_state_name import TaskRunFilterStateName
from .task_run_filter_state_type import TaskRunFilterStateType


class TaskRunFilterState(PrefectBaseModel, OperatorMixin):
    type: Optional[TaskRunFilterStateType]
    name: Optional[TaskRunFilterStateName]
