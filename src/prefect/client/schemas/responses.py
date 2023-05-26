import datetime
from typing import Any, Dict, List, Optional, TypeVar, Union
from typing_extensions import Literal
from uuid import UUID

from pydantic import Field

import prefect.client.schemas.objects as objects
from prefect._internal.schemas.bases import ObjectBaseModel, PrefectBaseModel
from prefect._internal.schemas.fields import CreatedBy, DateTimeTZ, UpdatedBy
from prefect._internal.schemas.transformations import FieldFrom, copy_model_fields
from prefect.client.schemas.schedules import SCHEDULE_TYPES
from prefect.utilities.collections import AutoEnum

R = TypeVar("R")


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

    state_type: objects.StateType = Field(default=..., description="The state type.")
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

    state: Optional[objects.State]
    status: SetStateStatus
    details: StateResponseDetails


class WorkerFlowRunResponse(PrefectBaseModel):
    class Config:
        arbitrary_types_allowed = True

    work_pool_id: UUID
    work_queue_id: UUID
    flow_run: objects.FlowRun


@copy_model_fields
class FlowRunResponse(ObjectBaseModel):
    name: str = FieldFrom(objects.FlowRun)
    flow_id: UUID = FieldFrom(objects.FlowRun)
    state_id: Optional[UUID] = FieldFrom(objects.FlowRun)
    deployment_id: Optional[UUID] = FieldFrom(objects.FlowRun)
    work_queue_name: Optional[str] = FieldFrom(objects.FlowRun)
    flow_version: Optional[str] = FieldFrom(objects.FlowRun)
    parameters: dict = FieldFrom(objects.FlowRun)
    idempotency_key: Optional[str] = FieldFrom(objects.FlowRun)
    context: dict = FieldFrom(objects.FlowRun)
    empirical_policy: objects.FlowRunPolicy = FieldFrom(objects.FlowRun)
    tags: List[str] = FieldFrom(objects.FlowRun)
    parent_task_run_id: Optional[UUID] = FieldFrom(objects.FlowRun)
    state_type: Optional[objects.StateType] = FieldFrom(objects.FlowRun)
    state_name: Optional[str] = FieldFrom(objects.FlowRun)
    run_count: int = FieldFrom(objects.FlowRun)
    expected_start_time: Optional[DateTimeTZ] = FieldFrom(objects.FlowRun)
    next_scheduled_start_time: Optional[DateTimeTZ] = FieldFrom(objects.FlowRun)
    start_time: Optional[DateTimeTZ] = FieldFrom(objects.FlowRun)
    end_time: Optional[DateTimeTZ] = FieldFrom(objects.FlowRun)
    total_run_time: datetime.timedelta = FieldFrom(objects.FlowRun)
    estimated_run_time: datetime.timedelta = FieldFrom(objects.FlowRun)
    estimated_start_time_delta: datetime.timedelta = FieldFrom(objects.FlowRun)
    auto_scheduled: bool = FieldFrom(objects.FlowRun)
    infrastructure_document_id: Optional[UUID] = FieldFrom(objects.FlowRun)
    infrastructure_pid: Optional[str] = FieldFrom(objects.FlowRun)
    created_by: Optional[CreatedBy] = FieldFrom(objects.FlowRun)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the flow run's work pool.",
        example="my-work-pool",
    )
    state: Optional[objects.State] = FieldFrom(objects.FlowRun)

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
class DeploymentResponse(ObjectBaseModel):
    name: str = FieldFrom(objects.Deployment)
    version: Optional[str] = FieldFrom(objects.Deployment)
    description: Optional[str] = FieldFrom(objects.Deployment)
    flow_id: UUID = FieldFrom(objects.Deployment)
    schedule: Optional[SCHEDULE_TYPES] = FieldFrom(objects.Deployment)
    is_schedule_active: bool = FieldFrom(objects.Deployment)
    infra_overrides: Dict[str, Any] = FieldFrom(objects.Deployment)
    parameters: Dict[str, Any] = FieldFrom(objects.Deployment)
    tags: List[str] = FieldFrom(objects.Deployment)
    work_queue_name: Optional[str] = FieldFrom(objects.Deployment)
    parameter_openapi_schema: Optional[Dict[str, Any]] = FieldFrom(objects.Deployment)
    path: Optional[str] = FieldFrom(objects.Deployment)
    pull_steps: Optional[List[dict]] = FieldFrom(objects.Deployment)
    entrypoint: Optional[str] = FieldFrom(objects.Deployment)
    manifest_path: Optional[str] = FieldFrom(objects.Deployment)
    storage_document_id: Optional[UUID] = FieldFrom(objects.Deployment)
    infrastructure_document_id: Optional[UUID] = FieldFrom(objects.Deployment)
    created_by: Optional[CreatedBy] = FieldFrom(objects.Deployment)
    updated_by: Optional[UpdatedBy] = FieldFrom(objects.Deployment)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
    )
