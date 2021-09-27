import datetime
from typing import Dict, List, Union
from uuid import UUID

from pydantic import Field
from typing_extensions import Literal
from prefect.orion import schemas
from prefect.orion.schemas.data import DataDocument
from prefect.orion.utilities.functions import ParameterSchema
from prefect.orion.utilities.schemas import ORMBaseModel, PrefectBaseModel


class Flow(ORMBaseModel):
    name: str = Field(..., example="my-flow")
    tags: List[str] = Field(default_factory=list, example=["tag-1", "tag-2"])

    # relationships
    # flow_runs: List["FlowRun"] = Field(default_factory=list)
    # deployments: List["Deployment"] = Field(default_factory=list)


class FlowRun(ORMBaseModel):
    flow_id: UUID
    state_id: UUID = None
    deployment_id: UUID = None
    flow_version: str = Field(None, example="1.0")
    parameters: dict = Field(default_factory=dict)
    idempotency_key: str = None
    context: dict = Field(default_factory=dict, example={"my_var": "my_val"})
    empirical_policy: dict = Field(default_factory=dict)
    empirical_config: dict = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list, example=["tag-1", "tag-2"])
    parent_task_run_id: UUID = None

    state_id: UUID = None
    state_type: schemas.states.StateType = None
    run_count: int = 0

    # the expected start time is set the first time
    # the run is placed in a state
    expected_start_time: datetime.datetime = None

    # the next scheduled start time will be populated
    # whenever the run is in a scheduled state
    next_scheduled_start_time: datetime.datetime = None
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None
    total_run_time: datetime.timedelta = datetime.timedelta(0)
    estimated_run_time: datetime.timedelta = datetime.timedelta(0)
    estimated_start_time_delta: datetime.timedelta = datetime.timedelta(0)
    auto_scheduled: bool = False

    # relationships
    # flow: Flow = None
    # task_runs: List["TaskRun"] = Field(default_factory=list)
    state: schemas.states.State = None
    # parent_task_run: "TaskRun" = None


class TaskRunPolicy(PrefectBaseModel):
    max_retries: int = 0
    retry_delay_seconds: float = 0


# TaskRunInput -- base class for task run inputs
# Constant(TaskRunInput)
# Parameter(TaskRunInput)
# TaskRunResult(TaskRunInput)


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
    input_type: Literal["task_run"] = "task_run"
    id: UUID


class Parameter(TaskRunInput):
    input_type: Literal["parameter"] = "parameter"
    name: str


class Constant(TaskRunInput):
    input_type: Literal["constant"] = "constant"
    type: str


class TaskRun(ORMBaseModel):
    flow_run_id: UUID
    task_key: str
    dynamic_key: str = None
    cache_key: str = None
    cache_expiration: datetime.datetime = None
    task_version: str = None
    empirical_policy: TaskRunPolicy = Field(default_factory=TaskRunPolicy)
    tags: List[str] = Field(default_factory=list, example=["tag-1", "tag-2"])
    state_id: UUID = None
    task_inputs: Dict[str, List[Union[TaskRunResult, Parameter, Constant]]] = Field(
        default_factory=dict
    )

    state_id: UUID = None
    state_type: schemas.states.StateType = None
    run_count: int = 0

    # the expected start time is set the first time
    # the run is placed in a state
    expected_start_time: datetime.datetime = None

    # the next scheduled start time will be populated
    # whenever the run is in a scheduled state
    next_scheduled_start_time: datetime.datetime = None
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None
    total_run_time: datetime.timedelta = datetime.timedelta(0)
    estimated_run_time: datetime.timedelta = datetime.timedelta(0)
    estimated_start_time_delta: datetime.timedelta = datetime.timedelta(0)

    # relationships
    # flow_run: FlowRun = None
    # subflow_runs: List[FlowRun] = Field(default_factory=list)
    state: schemas.states.State = None


class Deployment(ORMBaseModel):
    name: str
    flow_id: UUID
    flow_data: schemas.data.DataDocument
    schedule: schemas.schedules.SCHEDULE_TYPES = None
    is_schedule_active: bool = True
    tags: List[str] = Field(default_factory=list, example=["tag-1", "tag-2"])

    # flow: Flow = None


class SavedSearch(ORMBaseModel):
    name: str
    flow_filter_criteria: schemas.filters.FlowFilterCriteria = Field(
        default_factory=schemas.filters.FlowFilterCriteria
    )
    flow_run_filter_criteria: schemas.filters.FlowRunFilterCriteria = Field(
        default_factory=schemas.filters.FlowRunFilterCriteria
    )
    task_run_filter_criteria: schemas.filters.TaskRunFilterCriteria = Field(
        default_factory=schemas.filters.TaskRunFilterCriteria
    )
    deployment_filter_criteria: schemas.filters.DeploymentFilterCriteria = Field(
        default_factory=schemas.filters.DeploymentFilterCriteria
    )


Flow.update_forward_refs()
FlowRun.update_forward_refs()
