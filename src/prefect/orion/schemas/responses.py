"""
Schemas for special responses from the Orion API.
"""

import datetime
from typing import List, Optional, Union
from uuid import UUID

from pydantic import Field
from typing_extensions import TYPE_CHECKING, Literal

import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.orion.schemas.core import CreatedBy, FlowRunPolicy
from prefect.orion.utilities.schemas import (
    DateTimeTZ,
    FieldFrom,
    ORMBaseModel,
    PrefectBaseModel,
)
from prefect.utilities.collections import AutoEnum

if TYPE_CHECKING:
    import prefect.orion.database.orm_models


class SetStateStatus(AutoEnum):
    """Enumerates return statuses for setting run states."""

    ACCEPT = AutoEnum.auto()
    REJECT = AutoEnum.auto()
    ABORT = AutoEnum.auto()
    WAIT = AutoEnum.auto()


class StateAcceptDetails(PrefectBaseModel):
    """Details associated with an ACCEPT state transition."""

    type: Literal["accept_details"] = Field(
        default="accept_details",
        description="The type of state transition detail. Used to ensure pydantic does not coerce into a different type.",
    )


class StateRejectDetails(PrefectBaseModel):
    """Details associated with a REJECT state transition."""

    type: Literal["reject_details"] = Field(
        default="reject_details",
        description="The type of state transition detail. Used to ensure pydantic does not coerce into a different type.",
    )
    reason: Optional[str] = Field(
        default=None, description="The reason why the state transition was rejected."
    )


class StateAbortDetails(PrefectBaseModel):
    """Details associated with an ABORT state transition."""

    type: Literal["abort_details"] = Field(
        default="abort_details",
        description="The type of state transition detail. Used to ensure pydantic does not coerce into a different type.",
    )
    reason: Optional[str] = Field(
        default=None, description="The reason why the state transition was aborted."
    )


class StateWaitDetails(PrefectBaseModel):
    """Details associated with a WAIT state transition."""

    type: Literal["wait_details"] = Field(
        default="wait_details",
        description="The type of state transition detail. Used to ensure pydantic does not coerce into a different type.",
    )
    delay_seconds: int = Field(
        default=...,
        description="The length of time in seconds the client should wait before transitioning states.",
    )
    reason: Optional[str] = Field(
        default=None, description="The reason why the state transition should wait."
    )


class HistoryResponseState(PrefectBaseModel):
    """Represents a single state's history over an interval."""

    state_type: schemas.states.StateType = Field(
        default=..., description="The state type."
    )
    state_name: str = Field(default=..., description="The state name.")
    count_runs: int = Field(
        default=...,
        description="The number of runs in the specified state during the interval.",
    )
    sum_estimated_run_time: datetime.timedelta = Field(
        default=...,
        description="The total estimated run time of all runs during the interval.",
    )
    sum_estimated_lateness: datetime.timedelta = Field(
        default=...,
        description="The sum of differences between actual and expected start time during the interval.",
    )


class HistoryResponse(PrefectBaseModel):
    """Represents a history of aggregation states over an interval"""

    interval_start: DateTimeTZ = Field(
        default=..., description="The start date of the interval."
    )
    interval_end: DateTimeTZ = Field(
        default=..., description="The end date of the interval."
    )
    states: List[HistoryResponseState] = Field(
        default=..., description="A list of state histories during the interval."
    )


StateResponseDetails = Union[
    StateAcceptDetails, StateWaitDetails, StateRejectDetails, StateAbortDetails
]


class OrchestrationResult(PrefectBaseModel):
    """
    A container for the output of state orchestration.
    """

    state: Optional[schemas.states.State]
    status: SetStateStatus
    details: StateResponseDetails


class WorkerFlowRunResponse(PrefectBaseModel):
    class Config:
        arbitrary_types_allowed = True

    worker_pool_id: UUID
    worker_pool_queue_id: UUID
    flow_run: schemas.core.FlowRun


class FlowRunResponse(ORMBaseModel):

    name: str = FieldFrom(schemas.core.FlowRun)
    flow_id: UUID = FieldFrom(schemas.core.FlowRun)
    state_id: Optional[UUID] = FieldFrom(schemas.core.FlowRun)
    deployment_id: Optional[UUID] = FieldFrom(schemas.core.FlowRun)
    work_queue_name: Optional[str] = FieldFrom(schemas.core.FlowRun)
    flow_version: Optional[str] = FieldFrom(schemas.core.FlowRun)
    parameters: dict = FieldFrom(schemas.core.FlowRun)
    idempotency_key: Optional[str] = FieldFrom(schemas.core.FlowRun)
    context: dict = FieldFrom(schemas.core.FlowRun)
    empirical_policy: FlowRunPolicy = FieldFrom(schemas.core.FlowRun)
    tags: List[str] = FieldFrom(schemas.core.FlowRun)
    parent_task_run_id: Optional[UUID] = FieldFrom(schemas.core.FlowRun)
    state_type: Optional[schemas.states.StateType] = FieldFrom(schemas.core.FlowRun)
    state_name: Optional[str] = FieldFrom(schemas.core.FlowRun)
    run_count: int = FieldFrom(schemas.core.FlowRun)
    expected_start_time: Optional[DateTimeTZ] = FieldFrom(schemas.core.FlowRun)
    next_scheduled_start_time: Optional[DateTimeTZ] = FieldFrom(schemas.core.FlowRun)
    start_time: Optional[DateTimeTZ] = FieldFrom(schemas.core.FlowRun)
    end_time: Optional[DateTimeTZ] = FieldFrom(schemas.core.FlowRun)
    total_run_time: datetime.timedelta = FieldFrom(schemas.core.FlowRun)
    estimated_run_time: datetime.timedelta = FieldFrom(schemas.core.FlowRun)
    estimated_start_time_delta: datetime.timedelta = FieldFrom(schemas.core.FlowRun)
    auto_scheduled: bool = FieldFrom(schemas.core.FlowRun)
    infrastructure_document_id: Optional[UUID] = FieldFrom(schemas.core.FlowRun)
    infrastructure_pid: Optional[str] = FieldFrom(schemas.core.FlowRun)
    created_by: Optional[CreatedBy] = FieldFrom(schemas.core.FlowRun)
    worker_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the flow run's worker pool.",
        example="my-worker-pool",
    )
    worker_pool_queue_name: Optional[str] = Field(
        default=None,
        description="The name of the flow run's worker pool queue.",
        example="my-worker-pool-queue",
    )
    state: Optional[schemas.states.State] = FieldFrom(schemas.core.FlowRun)

    @classmethod
    async def from_orm_model(
        cls, session, orm_flow_run: "prefect.orion.database.orm_models.ORMFlowRun"
    ):
        response = cls.from_orm(orm_flow_run)
        if orm_flow_run.worker_pool_queue_id:
            worker_pool_queue = await models.workers.read_worker_pool_queue(
                session=session, worker_pool_queue_id=orm_flow_run.worker_pool_queue_id
            )
            response.worker_pool_queue_name = worker_pool_queue.name
            worker_pool = await models.workers.read_worker_pool(
                session=session, worker_pool_id=worker_pool_queue.worker_pool_id
            )
            response.worker_pool_name = worker_pool.name

        return response
