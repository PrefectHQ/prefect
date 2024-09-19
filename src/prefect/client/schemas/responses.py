import datetime
from typing import Any, Dict, List, Optional, TypeVar, Union
from uuid import UUID

from pydantic import ConfigDict, Field
from pydantic_extra_types.pendulum_dt import DateTime
from typing_extensions import Literal

import prefect.client.schemas.objects as objects
from prefect._internal.schemas.bases import ObjectBaseModel, PrefectBaseModel
from prefect._internal.schemas.fields import CreatedBy, UpdatedBy
from prefect.utilities.collections import AutoEnum
from prefect.utilities.names import generate_slug

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

    interval_start: DateTime = Field(
        default=..., description="The start date of the interval."
    )
    interval_end: DateTime = Field(
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
    model_config = ConfigDict(arbitrary_types_allowed=True)

    work_pool_id: UUID
    work_queue_id: UUID
    flow_run: objects.FlowRun


class FlowRunResponse(ObjectBaseModel):
    name: str = Field(
        default_factory=lambda: generate_slug(2),
        description=(
            "The name of the flow run. Defaults to a random slug if not specified."
        ),
        examples=["my-flow-run"],
    )
    flow_id: UUID = Field(default=..., description="The id of the flow being run.")
    state_id: Optional[UUID] = Field(
        default=None, description="The id of the flow run's current state."
    )
    deployment_id: Optional[UUID] = Field(
        default=None,
        description=(
            "The id of the deployment associated with this flow run, if available."
        ),
    )
    deployment_version: Optional[str] = Field(
        default=None,
        description="The version of the deployment associated with this flow run.",
        examples=["1.0"],
    )
    work_queue_name: Optional[str] = Field(
        default=None, description="The work queue that handled this flow run."
    )
    flow_version: Optional[str] = Field(
        default=None,
        description="The version of the flow executed in this flow run.",
        examples=["1.0"],
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Parameters for the flow run."
    )
    idempotency_key: Optional[str] = Field(
        default=None,
        description=(
            "An optional idempotency key for the flow run. Used to ensure the same flow"
            " run is not created multiple times."
        ),
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for the flow run.",
        examples=[{"my_var": "my_val"}],
    )
    empirical_policy: objects.FlowRunPolicy = Field(
        default_factory=objects.FlowRunPolicy,
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags on the flow run",
        examples=[["tag-1", "tag-2"]],
    )
    parent_task_run_id: Optional[UUID] = Field(
        default=None,
        description=(
            "If the flow run is a subflow, the id of the 'dummy' task in the parent"
            " flow used to track subflow state."
        ),
    )
    run_count: int = Field(
        default=0, description="The number of times the flow run was executed."
    )
    expected_start_time: Optional[DateTime] = Field(
        default=None,
        description="The flow run's expected start time.",
    )
    next_scheduled_start_time: Optional[DateTime] = Field(
        default=None,
        description="The next time the flow run is scheduled to start.",
    )
    start_time: Optional[DateTime] = Field(
        default=None, description="The actual start time."
    )
    end_time: Optional[DateTime] = Field(
        default=None, description="The actual end time."
    )
    total_run_time: datetime.timedelta = Field(
        default=datetime.timedelta(0),
        description=(
            "Total run time. If the flow run was executed multiple times, the time of"
            " each run will be summed."
        ),
    )
    estimated_run_time: datetime.timedelta = Field(
        default=datetime.timedelta(0),
        description="A real-time estimate of the total run time.",
    )
    estimated_start_time_delta: datetime.timedelta = Field(
        default=datetime.timedelta(0),
        description="The difference between actual and expected start time.",
    )
    auto_scheduled: bool = Field(
        default=False,
        description="Whether or not the flow run was automatically scheduled.",
    )
    infrastructure_document_id: Optional[UUID] = Field(
        default=None,
        description="The block document defining infrastructure to use this flow run.",
    )
    infrastructure_pid: Optional[str] = Field(
        default=None,
        description="The id of the flow run as returned by an infrastructure block.",
    )
    created_by: Optional[CreatedBy] = Field(
        default=None,
        description="Optional information about the creator of this flow run.",
    )
    work_queue_id: Optional[UUID] = Field(
        default=None, description="The id of the run's work pool queue."
    )

    work_pool_id: Optional[UUID] = Field(
        description="The work pool with which the queue is associated."
    )
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the flow run's work pool.",
        examples=["my-work-pool"],
    )
    state: Optional[objects.State] = Field(
        default=None,
        description="The state of the flow run.",
        examples=["objects.State(type=objects.StateType.COMPLETED)"],
    )
    job_variables: Optional[dict] = Field(
        default=None, description="Job variables for the flow run."
    )

    # These are server-side optimizations and should not be present on client models
    # TODO: Deprecate these fields

    state_type: Optional[objects.StateType] = Field(
        default=None, description="The type of the current flow run state."
    )
    state_name: Optional[str] = Field(
        default=None, description="The name of the current flow run state."
    )

    def __eq__(self, other: Any) -> bool:
        """
        Check for "equality" to another flow run schema

        Estimates times are rolling and will always change with repeated queries for
        a flow run so we ignore them during equality checks.
        """
        if isinstance(other, objects.FlowRun):
            exclude_fields = {"estimated_run_time", "estimated_start_time_delta"}
            return self.model_dump(exclude=exclude_fields) == other.model_dump(
                exclude=exclude_fields
            )
        return super().__eq__(other)


class DeploymentResponse(ObjectBaseModel):
    name: str = Field(default=..., description="The name of the deployment.")
    version: Optional[str] = Field(
        default=None, description="An optional version for the deployment."
    )
    description: Optional[str] = Field(
        default=None, description="A description for the deployment."
    )
    flow_id: UUID = Field(
        default=..., description="The flow id associated with the deployment."
    )
    concurrency_limit: Optional[int] = Field(
        default=None,
        description="DEPRECATED: Prefer `global_concurrency_limit`. Will always be None for backwards compatibility. Will be removed after December 2024.",
        deprecated=True,
    )
    global_concurrency_limit: Optional["GlobalConcurrencyLimitResponse"] = Field(
        default=None,
        description="The global concurrency limit object for enforcing the maximum number of flow runs that can be active at once.",
    )
    concurrency_options: Optional[objects.ConcurrencyOptions] = Field(
        default=None,
        description="The concurrency options for the deployment.",
    )
    paused: bool = Field(
        default=False, description="Whether or not the deployment is paused."
    )
    concurrency_options: Optional[objects.ConcurrencyOptions] = Field(
        default=None,
        description="The concurrency options for the deployment.",
    )
    schedules: List[objects.DeploymentSchedule] = Field(
        default_factory=list, description="A list of schedules for the deployment."
    )
    job_variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Overrides to apply to flow run infrastructure at runtime.",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for flow runs scheduled by the deployment.",
    )
    pull_steps: Optional[List[dict]] = Field(
        default=None,
        description="Pull steps for cloning and running this deployment.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags for the deployment",
        examples=[["tag-1", "tag-2"]],
    )
    work_queue_name: Optional[str] = Field(
        default=None,
        description=(
            "The work queue for the deployment. If no work queue is set, work will not"
            " be scheduled."
        ),
    )
    last_polled: Optional[DateTime] = Field(
        default=None,
        description="The last time the deployment was polled for status updates.",
    )
    parameter_openapi_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The parameter schema of the flow, including defaults.",
    )
    path: Optional[str] = Field(
        default=None,
        description=(
            "The path to the working directory for the workflow, relative to remote"
            " storage or an absolute path."
        ),
    )
    entrypoint: Optional[str] = Field(
        default=None,
        description=(
            "The path to the entrypoint for the workflow, relative to the `path`."
        ),
    )
    storage_document_id: Optional[UUID] = Field(
        default=None,
        description="The block document defining storage used for this flow.",
    )
    infrastructure_document_id: Optional[UUID] = Field(
        default=None,
        description="The block document defining infrastructure to use for flow runs.",
    )
    created_by: Optional[CreatedBy] = Field(
        default=None,
        description="Optional information about the creator of this deployment.",
    )
    updated_by: Optional[UpdatedBy] = Field(
        default=None,
        description="Optional information about the updater of this deployment.",
    )
    work_queue_id: UUID = Field(
        default=None,
        description=(
            "The id of the work pool queue to which this deployment is assigned."
        ),
    )
    enforce_parameter_schema: bool = Field(
        default=True,
        description=(
            "Whether or not the deployment should enforce the parameter schema."
        ),
    )
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
    )
    status: Optional[objects.DeploymentStatus] = Field(
        default=None,
        description="Current status of the deployment.",
    )


class MinimalConcurrencyLimitResponse(PrefectBaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    name: str
    limit: int


class GlobalConcurrencyLimitResponse(ObjectBaseModel):
    """
    A response object for global concurrency limits.
    """

    active: bool = Field(
        default=True, description="Whether the global concurrency limit is active."
    )
    name: str = Field(
        default=..., description="The name of the global concurrency limit."
    )
    limit: int = Field(default=..., description="The concurrency limit.")
    active_slots: int = Field(default=..., description="The number of active slots.")
    slot_decay_per_second: float = Field(
        default=2.0,
        description="The decay rate for active slots when used as a rate limit.",
    )
