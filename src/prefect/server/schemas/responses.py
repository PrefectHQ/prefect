"""
Schemas for special responses from the Prefect REST API.
"""

import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field
else:
    from pydantic import Field

from typing_extensions import TYPE_CHECKING, Literal

import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect._internal.compatibility.deprecated import DeprecatedInfraOverridesField
from prefect.server.schemas.core import (
    CreatedBy,
    FlowRunPolicy,
    UpdatedBy,
    WorkQueueStatusDetail,
)
from prefect.server.utilities.schemas.bases import ORMBaseModel, PrefectBaseModel
from prefect.server.utilities.schemas.fields import DateTimeTZ
from prefect.utilities.collections import AutoEnum
from prefect.utilities.names import generate_slug

if TYPE_CHECKING:
    from prefect.server.database.orm_models import ORMDeployment, ORMFlowRun, ORMWorker

WORK_QUEUE_LAST_POLLED_TIMEOUT_SECONDS = 60


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


class FlowRunResponse(ORMBaseModel):
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
    work_queue_id: Optional[UUID] = Field(
        default=None, description="The id of the run's work pool queue."
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
    empirical_policy: FlowRunPolicy = Field(
        default_factory=FlowRunPolicy,
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
    state_type: Optional[schemas.states.StateType] = Field(
        default=None, description="The type of the current flow run state."
    )
    state_name: Optional[str] = Field(
        default=None, description="The name of the current flow run state."
    )
    run_count: int = Field(
        default=0, description="The number of times the flow run was executed."
    )
    expected_start_time: Optional[DateTimeTZ] = Field(
        default=None,
        description="The flow run's expected start time.",
    )
    next_scheduled_start_time: Optional[DateTimeTZ] = Field(
        default=None,
        description="The next time the flow run is scheduled to start.",
    )
    start_time: Optional[DateTimeTZ] = Field(
        default=None, description="The actual start time."
    )
    end_time: Optional[DateTimeTZ] = Field(
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
    work_pool_id: Optional[UUID] = Field(
        default=None,
        description="The id of the flow run's work pool.",
    )
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the flow run's work pool.",
        examples=["my-work-pool"],
    )
    state: Optional[schemas.states.State] = Field(
        default=None, description="The current state of the flow run."
    )
    job_variables: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Variables used as overrides in the base job template",
    )

    @classmethod
    def from_orm(cls, orm_flow_run: "ORMFlowRun"):
        response = super().from_orm(orm_flow_run)
        if orm_flow_run.work_queue:
            response.work_queue_id = orm_flow_run.work_queue.id
            response.work_queue_name = orm_flow_run.work_queue.name
            if orm_flow_run.work_queue.work_pool:
                response.work_pool_id = orm_flow_run.work_queue.work_pool.id
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


class DeploymentResponse(DeprecatedInfraOverridesField, ORMBaseModel):
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
    schedule: Optional[schemas.schedules.SCHEDULE_TYPES] = Field(
        default=None, description="A schedule for the deployment."
    )
    is_schedule_active: bool = Field(
        default=True, description="Whether or not the deployment schedule is active."
    )
    paused: bool = Field(
        default=False, description="Whether or not the deployment is paused."
    )
    schedules: List[schemas.core.DeploymentSchedule] = Field(
        default_factory=list, description="A list of schedules for the deployment."
    )
    job_variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Overrides to apply to the base infrastructure block at runtime.",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for flow runs scheduled by the deployment.",
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
    last_polled: Optional[DateTimeTZ] = Field(
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
    pull_steps: Optional[List[dict]] = Field(
        default=None, description="Pull steps for cloning and running this deployment."
    )
    entrypoint: Optional[str] = Field(
        default=None,
        description=(
            "The path to the entrypoint for the workflow, relative to the `path`."
        ),
    )
    manifest_path: Optional[str] = Field(
        default=None,
        description=(
            "The path to the flow's manifest file, relative to the chosen storage."
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
    work_pool_name: Optional[str] = Field(
        default=None, description="The name of the deployment's work pool."
    )
    status: Optional[schemas.statuses.DeploymentStatus] = Field(
        default=schemas.statuses.DeploymentStatus.NOT_READY,
        description="Whether the deployment is ready to run flows.",
    )
    enforce_parameter_schema: bool = Field(
        default=False,
        description=(
            "Whether or not the deployment should enforce the parameter schema."
        ),
    )

    @classmethod
    def from_orm(cls, orm_deployment: "ORMDeployment"):
        response = super().from_orm(orm_deployment)

        if orm_deployment.work_queue:
            response.work_queue_name = orm_deployment.work_queue.name
            if orm_deployment.work_queue.work_pool:
                response.work_pool_name = orm_deployment.work_queue.work_pool.name

        # Populate `schedule` and `is_schedule_active` for backwards
        # compatibility with clients that do not support multiple
        # schedules. The order of the schedules is determined by the
        # relationship on Deployment.schedules, so we just take the first
        # schedule as the primary schedule.
        if orm_deployment.schedules:
            response.schedule = orm_deployment.schedules[0].schedule
        else:
            response.schedule = None

        response.is_schedule_active = not bool(orm_deployment.paused)

        return response


class WorkQueueResponse(schemas.core.WorkQueue):
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the work pool the work pool resides within.",
    )
    status: Optional[schemas.statuses.WorkQueueStatus] = Field(
        default=None, description="The queue status."
    )

    @classmethod
    def from_orm(cls, orm_work_queue):
        response = super().from_orm(orm_work_queue)
        if orm_work_queue.work_pool:
            response.work_pool_name = orm_work_queue.work_pool.name

        if response.is_paused:
            response.status = schemas.statuses.WorkQueueStatus.PAUSED
        else:
            unready_at = datetime.datetime.now(
                tz=datetime.timezone.utc
            ) - datetime.timedelta(seconds=WORK_QUEUE_LAST_POLLED_TIMEOUT_SECONDS)
            if response.last_polled and response.last_polled > unready_at:
                response.status = schemas.statuses.WorkQueueStatus.READY
            else:
                response.status = schemas.statuses.WorkQueueStatus.NOT_READY
        return response


class WorkQueueWithStatus(WorkQueueResponse, WorkQueueStatusDetail):
    """Combines a work queue and its status details into a single object"""


class WorkPoolResponse(schemas.core.WorkPool):
    status: Optional[schemas.statuses.WorkPoolStatus] = Field(
        default=None, description="The current status of the work pool."
    )

    @classmethod
    async def from_orm(cls, orm_work_pool, session):
        work_pool = super().from_orm(orm_work_pool)
        if work_pool.type == "prefect-agent":
            work_pool.status = None
        elif work_pool.is_paused:
            work_pool.status = schemas.statuses.WorkPoolStatus.PAUSED
        else:
            read_workers = await models.workers.read_workers(
                session=session,
                work_pool_id=work_pool.id,
            )
            online_workers = [
                worker
                for worker in read_workers
                if schemas.responses.WorkerResponse.from_orm(worker).status
                == schemas.statuses.WorkerStatus.ONLINE
            ]
            if len(online_workers) > 0:
                work_pool.status = schemas.statuses.WorkPoolStatus.READY
            else:
                work_pool.status = schemas.statuses.WorkPoolStatus.NOT_READY
        return work_pool


DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30
INACTIVITY_HEARTBEAT_MULTIPLE = 3


class WorkerResponse(schemas.core.Worker):
    status: schemas.statuses.WorkerStatus = Field(
        schemas.statuses.WorkerStatus.OFFLINE,
        description="Current status of the worker.",
    )

    @classmethod
    def from_orm(cls, orm_worker: "ORMWorker") -> "WorkerResponse":
        worker = super().from_orm(orm_worker)
        offline_horizon = datetime.datetime.now(
            tz=datetime.timezone.utc
        ) - datetime.timedelta(
            seconds=(
                worker.heartbeat_interval_seconds or DEFAULT_HEARTBEAT_INTERVAL_SECONDS
            )
            * INACTIVITY_HEARTBEAT_MULTIPLE
        )
        if worker.last_heartbeat_time > offline_horizon:
            worker.status = schemas.statuses.WorkerStatus.ONLINE
        else:
            worker.status = schemas.statuses.WorkerStatus.OFFLINE

        return worker
