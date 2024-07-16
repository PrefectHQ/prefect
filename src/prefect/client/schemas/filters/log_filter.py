from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .log_filter_flow_run_id import LogFilterFlowRunId
from .log_filter_level import LogFilterLevel
from .log_filter_task_run_id import LogFilterTaskRunId
from .log_filter_timestamp import LogFilterTimestamp
from .operator_mixin import OperatorMixin


class LogFilter(PrefectBaseModel, OperatorMixin):
    """Filter logs. Only logs matching all criteria will be returned"""

    level: Optional[LogFilterLevel] = Field(
        default=None, description="Filter criteria for `Log.level`"
    )
    timestamp: Optional[LogFilterTimestamp] = Field(
        default=None, description="Filter criteria for `Log.timestamp`"
    )
    flow_run_id: Optional[LogFilterFlowRunId] = Field(
        default=None, description="Filter criteria for `Log.flow_run_id`"
    )
    task_run_id: Optional[LogFilterTaskRunId] = Field(
        default=None, description="Filter criteria for `Log.task_run_id`"
    )
