"""
Schemas for special responses from the Prefect REST API.
"""

import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import Field
from typing_extensions import TYPE_CHECKING, Literal

import prefect.server.schemas as schemas
from prefect.server.schemas.core import CreatedBy, FlowRunPolicy, UpdatedBy
from prefect.server.utilities.schemas import (
    DateTimeTZ,
    FieldFrom,
    ORMBaseModel,
    PrefectBaseModel,
    copy_model_fields,
)
from prefect.utilities.collections import AutoEnum

if TYPE_CHECKING:
    import prefect.server.database.orm_models


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
        description=(
            "The type of state transition detail. Used to ensure pydantic does not"
            " coerce into a different type."
        ),
    )


class StateRejectDetails(PrefectBaseModel):
    """Details associated with a REJECT state transition."""

    type: Literal["reject_details"] = Field(
        default="reject_details",
        description=(
            "The type of state transition detail. Used to ensure pydantic does not"
            " coerce into a different type."
        ),
    )
    reason: Optional[str] = Field(
        default=None, description="The reason why the state transition was rejected."
    )


class StateAbortDetails(PrefectBaseModel):
    """Details associated with an ABORT state transition."""

    type: Literal["abort_details"] = Field(
        default="abort_details",
        description=(
            "The type of state transition detail. Used to ensure pydantic does not"
            " coerce into a different type."
        ),
    )
    reason: Optional[str] = Field(
        default=None, description="The reason why the state transition was aborted."
    )


class StateWaitDetails(PrefectBaseModel):
    """Details associated with a WAIT state transition."""

    type: Literal["wait_details"] = Field(
        default="wait_details",
        description=(
            "The type of state transition detail. Used to ensure pydantic does not"
            " coerce into a different type."
        ),
    )
    delay_seconds: int = Field(
        default=...,
        description=(
            "The length of time in seconds the client should wait before transitioning"
            " states."
        ),
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
        description=(
            "The sum of differences between actual and expected start time during the"
            " interval."
        ),
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

    work_pool_id: UUID
    work_queue_id: UUID
    flow_run: schemas.core.FlowRun


@copy_model_fields
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
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the flow run's work pool.",
        example="my-work-pool",
    )
    state: Optional[schemas.states.State] = FieldFrom(schemas.core.FlowRun)

    @classmethod
    def from_orm(cls, orm_flow_run: "prefect.server.database.orm_models.ORMFlowRun"):
        response = super().from_orm(orm_flow_run)
        if orm_flow_run.work_queue:
            response.work_queue_name = orm_flow_run.work_queue.name
            if orm_flow_run.work_queue.work_pool:
                response.work_pool_name = orm_flow_run.work_queue.work_pool.name

        return response

    def __eq__(self, other: Any) -> bool:
        """
        Check for "equality" to another flow run schema

        Estimates times are rolling and will always change with repeated queries for
        a flow run so we ignore them during equality checks.
        """
        if isinstance(other, FlowRunResponse):
            exclude_fields = {"estimated_run_time", "estimated_start_time_delta"}
            return self.dict(exclude=exclude_fields) == other.dict(
                exclude=exclude_fields
            )
        return super().__eq__(other)


@copy_model_fields
class DeploymentResponse(ORMBaseModel):
    name: str = FieldFrom(schemas.core.Deployment)
    version: Optional[str] = FieldFrom(schemas.core.Deployment)
    description: Optional[str] = FieldFrom(schemas.core.Deployment)
    flow_id: UUID = FieldFrom(schemas.core.Deployment)
    schedule: Optional[schemas.schedules.SCHEDULE_TYPES] = FieldFrom(
        schemas.core.Deployment
    )
    is_schedule_active: bool = FieldFrom(schemas.core.Deployment)
    infra_overrides: Dict[str, Any] = FieldFrom(schemas.core.Deployment)
    parameters: Dict[str, Any] = FieldFrom(schemas.core.Deployment)
    tags: List[str] = FieldFrom(schemas.core.Deployment)
    work_queue_name: Optional[str] = FieldFrom(schemas.core.Deployment)
    parameter_openapi_schema: Optional[Dict[str, Any]] = FieldFrom(
        schemas.core.Deployment
    )
    path: Optional[str] = FieldFrom(schemas.core.Deployment)
    entrypoint: Optional[str] = FieldFrom(schemas.core.Deployment)
    manifest_path: Optional[str] = FieldFrom(schemas.core.Deployment)
    storage_document_id: Optional[UUID] = FieldFrom(schemas.core.Deployment)
    infrastructure_document_id: Optional[UUID] = FieldFrom(schemas.core.Deployment)
    created_by: Optional[CreatedBy] = FieldFrom(schemas.core.Deployment)
    updated_by: Optional[UpdatedBy] = FieldFrom(schemas.core.Deployment)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
    )

    @classmethod
    def from_orm(
        cls, orm_deployment: "prefect.server.database.orm_models.ORMDeployment"
    ):
        response = super().from_orm(orm_deployment)
        if orm_deployment.work_queue:
            response.work_queue_name = orm_deployment.work_queue.name
            if orm_deployment.work_queue.work_pool:
                response.work_pool_name = orm_deployment.work_queue.work_pool.name

        return response
