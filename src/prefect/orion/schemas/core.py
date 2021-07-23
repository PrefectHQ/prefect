"""
"Full" schemas for working with data objects internally
"""

import datetime
from enum import auto
from typing import List, Dict
from uuid import UUID

from pydantic import BaseModel, Field

from prefect.orion.utilities.functions import ParameterSchema
from prefect.orion.utilities.schemas import PrefectBaseModel
from prefect.orion.utilities.enum import AutoEnum


class APIBaseModel(PrefectBaseModel):
    class Config:
        orm_mode = True

    id: UUID
    created: datetime.datetime
    updated: datetime.datetime


class Flow(APIBaseModel):
    name: str = Field(..., example="my-flow")
    tags: List[str] = Field(default_factory=list, example=["tag-1", "tag-2"])
    parameters: ParameterSchema = Field(default_factory=ParameterSchema)


class FlowRunMetadata(PrefectBaseModel):
    is_subflow: bool = False


class FlowRun(APIBaseModel):
    flow_id: UUID
    flow_version: str = Field(..., example="v1.0")
    parameters: dict = Field(default_factory=dict)
    parent_task_run_id: UUID = None
    context: dict = Field(default_factory=dict, example={"my_var": "my_val"})
    empirical_policy: dict = Field(default_factory=dict)
    empirical_config: dict = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list, example=["tag-1", "tag-2"])
    flow_run_metadata: FlowRunMetadata = Field(default_factory=FlowRunMetadata)


class StateType(AutoEnum):
    Running = auto()
    Completed = auto()
    Failed = auto()
    Scheduled = auto()
    Pending = auto()


class StateDetails(PrefectBaseModel):
    flow_run_id: UUID = None
    task_run_id: UUID = None


class RunDetails(PrefectBaseModel):
    previous_state_id: UUID = None
    run_count: int = 0
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None
    total_run_time_seconds: float = 0.0
    total_time_seconds: float = 0.0
    last_run_time: float = 0.0


class FlowRunState(APIBaseModel):
    name: str
    type: StateType
    timestamp: datetime.datetime
    message: str = Field("", example="Flow run started")
    state_details: StateDetails = Field(default_factory=StateDetails)
    run_details: RunDetails = Field(default_factory=RunDetails)
    # TODO implement this when we do ResultLocations
    data_location: dict = Field(default_factory=dict)


class TaskRunMetadata(PrefectBaseModel):
    is_subflow: bool = False


class TaskRun(APIBaseModel):
    flow_run_id: UUID
    task_key: str
    dynamic_key: str = None
    cache_key: str = None
    cache_expiration: datetime.datetime = None
    task_version: str = None
    empirical_policy: dict = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list, example=["tag-1", "tag-2"])
    task_inputs: ParameterSchema = Field(default_factory=ParameterSchema)
    upstream_task_run_ids: Dict[str, UUID] = Field(default_factory=dict)
    task_run_metadata: TaskRunMetadata = Field(default_factory=TaskRunMetadata)
