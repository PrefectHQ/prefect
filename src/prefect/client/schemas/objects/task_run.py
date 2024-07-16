import datetime
from typing import (
    Dict,
    List,
    Optional,
    Union,
)
from uuid import UUID

from pydantic import (
    Field,
    field_validator,
)
from pydantic_extra_types.pendulum_dt import DateTime

from prefect._internal.schemas.bases import ObjectBaseModel
from prefect._internal.schemas.validators import (
    get_or_create_run_name,
)
from prefect.utilities.names import generate_slug

from .constant import Constant
from .parameter import Parameter
from .state import State
from .state_type import StateType
from .task_run_policy import TaskRunPolicy
from .task_run_result import TaskRunResult


class TaskRun(ObjectBaseModel):
    name: str = Field(
        default_factory=lambda: generate_slug(2), examples=["my-task-run"]
    )
    flow_run_id: Optional[UUID] = Field(
        default=None, description="The flow run id of the task run."
    )
    task_key: str = Field(
        default=..., description="A unique identifier for the task being run."
    )
    dynamic_key: str = Field(
        default=...,
        description=(
            "A dynamic key used to differentiate between multiple runs of the same task"
            " within the same flow run."
        ),
    )
    cache_key: Optional[str] = Field(
        default=None,
        description=(
            "An optional cache key. If a COMPLETED state associated with this cache key"
            " is found, the cached COMPLETED state will be used instead of executing"
            " the task run."
        ),
    )
    cache_expiration: Optional[DateTime] = Field(
        default=None, description="Specifies when the cached state should expire."
    )
    task_version: Optional[str] = Field(
        default=None, description="The version of the task being run."
    )
    empirical_policy: TaskRunPolicy = Field(
        default_factory=TaskRunPolicy,
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of tags for the task run.",
        examples=[["tag-1", "tag-2"]],
    )
    state_id: Optional[UUID] = Field(
        default=None, description="The id of the current task run state."
    )
    task_inputs: Dict[str, List[Union[TaskRunResult, Parameter, Constant]]] = Field(
        default_factory=dict,
        description=(
            "Tracks the source of inputs to a task run. Used for internal bookkeeping. "
            "Note the special __parents__ key, used to indicate a parent/child "
            "relationship that may or may not include an input or wait_for semantic."
        ),
    )
    state_type: Optional[StateType] = Field(
        default=None, description="The type of the current task run state."
    )
    state_name: Optional[str] = Field(
        default=None, description="The name of the current task run state."
    )
    run_count: int = Field(
        default=0, description="The number of times the task run has been executed."
    )
    flow_run_run_count: int = Field(
        default=0,
        description=(
            "If the parent flow has retried, this indicates the flow retry this run is"
            " associated with."
        ),
    )
    expected_start_time: Optional[DateTime] = Field(
        default=None,
        description="The task run's expected start time.",
    )

    # the next scheduled start time will be populated
    # whenever the run is in a scheduled state
    next_scheduled_start_time: Optional[DateTime] = Field(
        default=None,
        description="The next time the task run is scheduled to start.",
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
            "Total run time. If the task run was executed multiple times, the time of"
            " each run will be summed."
        ),
    )
    estimated_run_time: datetime.timedelta = Field(
        default=datetime.timedelta(0),
        description="A real-time estimate of total run time.",
    )
    estimated_start_time_delta: datetime.timedelta = Field(
        default=datetime.timedelta(0),
        description="The difference between actual and expected start time.",
    )

    state: Optional[State] = Field(
        default=None,
        description="The state of the task run.",
        examples=["State(type=StateType.COMPLETED)"],
    )

    @field_validator("name", mode="before")
    @classmethod
    def set_default_name(cls, name):
        return get_or_create_run_name(name)
