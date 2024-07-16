from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .operator_mixin import OperatorMixin
from .worker_filter_last_heartbeat_time import WorkerFilterLastHeartbeatTime


class WorkerFilter(PrefectBaseModel, OperatorMixin):
    # worker_config_id: Optional[WorkerFilterWorkPoolId] = Field(
    #     default=None, description="Filter criteria for `Worker.worker_config_id`"
    # )

    last_heartbeat_time: Optional[WorkerFilterLastHeartbeatTime] = Field(
        default=None,
        description="Filter criteria for `Worker.last_heartbeat_time`",
    )
