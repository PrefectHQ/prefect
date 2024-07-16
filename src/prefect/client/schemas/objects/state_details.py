from typing import (
    Dict,
    Optional,
)
from uuid import UUID

from pydantic_extra_types.pendulum_dt import DateTime

from prefect._internal.schemas.bases import PrefectBaseModel


class StateDetails(PrefectBaseModel):
    flow_run_id: Optional[UUID] = None
    task_run_id: Optional[UUID] = None
    # for task runs that represent subflows, the subflow's run ID
    child_flow_run_id: Optional[UUID] = None
    scheduled_time: Optional[DateTime] = None
    cache_key: Optional[str] = None
    cache_expiration: Optional[DateTime] = None
    deferred: Optional[bool] = None
    untrackable_result: bool = False
    pause_timeout: Optional[DateTime] = None
    pause_reschedule: bool = False
    pause_key: Optional[str] = None
    run_input_keyset: Optional[Dict[str, str]] = None
    refresh_cache: Optional[bool] = None
    retriable: Optional[bool] = None
    transition_id: Optional[UUID] = None
    task_parameters_id: Optional[UUID] = None