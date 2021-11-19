"""
Full schemas of Orion API objects.
"""

import datetime
from typing import Any, Dict, List, Union
from uuid import UUID

from pydantic import Field, validator
import coolname
from typing_extensions import Literal
from prefect.orion import schemas
from prefect.orion.utilities.schemas import ORMBaseModel, PrefectBaseModel


class Flow(ORMBaseModel):
    """An ORM representation of flow data."""

    name: str = Field(..., description="The name of the flow", example="my-flow")
    tags: List[str] = Field(
        default_factory=list,
        description="A list of flow tags",
        example=["tag-1", "tag-2"],
    )

    # relationships
    # flow_runs: List["FlowRun"] = Field(default_factory=list)
    # deployments: List["Deployment"] = Field(default_factory=list)


class FlowRun(ORMBaseModel):
    """An ORM representation of flow run data."""

    name: str = Field(
        default_factory=lambda: coolname.generate_slug(2),
        description="The name of the flow run. Defaults to a random slug if not specified.",
        example="my-flow-run",
    )
    flow_id: UUID = Field(..., description="The id of the flow being run.")
    state_id: UUID = Field(None, description="The id of the flow run's current state.")
    deployment_id: UUID = Field(
        None,
        description="The id of the deployment associated with this flow run, if available.",
    )
    flow_version: str = Field(
        None,
        description="The version of the flow executed in this flow run.",
        example="1.0",
    )
    parameters: dict = Field(
        default_factory=dict, description="Parameters for the flow run."
    )
    idempotency_key: str = Field(
        None,
        description="An optional idempotency key for the flow run. Used to ensure the same flow run is not created multiple times.",
    )
    context: dict = Field(
        default_factory=dict,
        description="Additional context for the flow run.",
        example={"my_var": "my_val"},
    )
    empirical_policy: dict = Field(default_factory=dict)
    empirical_config: dict = Field(default_factory=dict)
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags on the flow run",
        example=["tag-1", "tag-2"],
    )
    parent_task_run_id: UUID = Field(
        None,
        description="If the flow run is a subflow, the id of the 'dummy' task in the parent flow used to track subflow state.",
    )

    state_type: schemas.states.StateType = Field(
        None, description="The type of the current flow run state."
    )
    run_count: int = Field(
        0, description="The number of times the flow run was executed."
    )

    expected_start_time: datetime.datetime = Field(
        None,
        description="The flow run's expected start time.",
    )

    next_scheduled_start_time: datetime.datetime = Field(
        None,
        description="The next time the flow run is scheduled to start.",
    )
    start_time: datetime.datetime = Field(None, description="The actual start time.")
    end_time: datetime.datetime = Field(None, description="The actual end time.")
    total_run_time: datetime.timedelta = Field(
        datetime.timedelta(0),
        description="Total run time. If the flow run was executed multiple times, the time of each run will be summed.",
    )
    estimated_run_time: datetime.timedelta = Field(
        datetime.timedelta(0), description="A real-time estimate of the total run time."
    )
    estimated_start_time_delta: datetime.timedelta = Field(
        datetime.timedelta(0),
        description="The difference between actual and expected start time.",
    )
    auto_scheduled: bool = Field(
        False, description="Whether or not the flow run was automatically scheduled."
    )

    # relationships
    # flow: Flow = None
    # task_runs: List["TaskRun"] = Field(default_factory=list)
    state: schemas.states.State = Field(
        None, description="The current state of the flow run."
    )
    # parent_task_run: "TaskRun" = None

    @validator("name", pre=True)
    def set_name(cls, name):
        return name or coolname.generate_slug(2)

    def __eq__(self, other: Any) -> bool:
        """
        Check for "equality" to another flow run schema

        Estimates times are rolling and will always change with repeated queries for
        a flow run so we ignore them during equality checks.
        """
        if isinstance(other, FlowRun):
            exclude_fields = {"estimated_run_time", "estimated_start_time_delta"}
            return self.dict(exclude=exclude_fields) == other.dict(
                exclude=exclude_fields
            )
        return super().__eq__(other)


class TaskRunPolicy(PrefectBaseModel):
    """Defines of how a task run should retry."""

    max_retries: int = 0
    retry_delay_seconds: float = 0


class TaskRunInput(PrefectBaseModel):
    """
    Base class for classes that represent inputs to task runs, which
    could include, constants, parameters, or other task runs.
    """

    # freeze TaskRunInputs to allow them to be placed in sets
    class Config:
        frozen = True

    input_type: str


class TaskRunResult(TaskRunInput):
    """Represents a task run result input to another task run."""

    input_type: Literal["task_run"] = "task_run"
    id: UUID


class Parameter(TaskRunInput):
    """Represents a parameter input to a task run."""

    input_type: Literal["parameter"] = "parameter"
    name: str


class Constant(TaskRunInput):
    """Represents constant input value to a task run."""

    input_type: Literal["constant"] = "constant"
    type: str


class TaskRun(ORMBaseModel):
    """An ORM representation of task run data."""

    name: str = Field(
        default_factory=lambda: coolname.generate_slug(2), example="my-task-run"
    )
    flow_run_id: UUID = Field(..., description="The flow run id of the task run.")
    task_key: str = Field(
        ..., description="A unique identifier for the task being run."
    )
    dynamic_key: str = Field(
        ...,
        description="A dynamic key used to differentiate between multiple runs of the same task within the same flow run.",
    )
    cache_key: str = Field(
        None,
        description="An optional cache key. If a COMPLETED state associated with this cache key is found, the cached COMPLETED state will be used instead of executing the task run.",
    )
    cache_expiration: datetime.datetime = Field(
        None, description="Specifies when the cached state should expire."
    )
    task_version: str = Field(None, description="The version of the task being run.")
    empirical_policy: TaskRunPolicy = Field(
        default_factory=TaskRunPolicy,
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags for the task run.",
        example=["tag-1", "tag-2"],
    )
    state_id: UUID = Field(None, description="The id of the current task run state.")
    task_inputs: Dict[str, List[Union[TaskRunResult, Parameter, Constant]]] = Field(
        default_factory=dict,
        description="Tracks the source of inputs to a task run. Used for internal bookkeeping.",
    )

    state_type: schemas.states.StateType = Field(
        None, description="The type of the current task run state."
    )
    run_count: int = Field(
        0, description="The number of times the task run has been executed."
    )

    expected_start_time: datetime.datetime = Field(
        None,
        description="The task run's expected start time.",
    )

    # the next scheduled start time will be populated
    # whenever the run is in a scheduled state
    next_scheduled_start_time: datetime.datetime = Field(
        None,
        description="The next time the task run is scheduled to start.",
    )
    start_time: datetime.datetime = Field(None, description="The actual start time.")
    end_time: datetime.datetime = Field(None, description="The actual end time.")
    total_run_time: datetime.timedelta = Field(
        datetime.timedelta(0),
        description="Total run time. If the task run was executed multiple times, the time of each run will be summed.",
    )
    estimated_run_time: datetime.timedelta = Field(
        datetime.timedelta(0), description="A real-time estimate of total run time."
    )
    estimated_start_time_delta: datetime.timedelta = Field(
        datetime.timedelta(0),
        description="The difference between actual and expected start time.",
    )

    # relationships
    # flow_run: FlowRun = None
    # subflow_runs: List[FlowRun] = Field(default_factory=list)
    state: schemas.states.State = Field(None, description="The current task run state.")

    @validator("name", pre=True)
    def set_name(cls, name):
        return name or coolname.generate_slug(2)


class Deployment(ORMBaseModel):
    """An ORM representation of deployment data."""

    name: str = Field(..., description="The name of the deployment.")
    flow_id: UUID = Field(
        ..., description="The flow id associated with the deployment."
    )
    flow_data: schemas.data.DataDocument = Field(
        ..., description="A data document representing the flow code to execute."
    )
    schedule: schemas.schedules.SCHEDULE_TYPES = Field(
        None, description="A schedule for the deployment."
    )
    is_schedule_active: bool = Field(
        True, description="Whether or not the deployment schedule is active."
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for flow runs scheduled by the deployment.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags for the deployment",
        example=["tag-1", "tag-2"],
    )

    # flow: Flow = None


class SavedSearch(ORMBaseModel):
    """An ORM representation of saved search data. Represents a set of filter criteria."""

    name: str = Field(..., description="The name of the saved search.")
    filters: dict = Field(
        default_factory=dict, description="The filter set for the saved search."
    )


Flow.update_forward_refs()
FlowRun.update_forward_refs()
