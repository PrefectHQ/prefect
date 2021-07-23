import datetime
from enum import auto
from typing import List
from uuid import UUID

import pendulum
from pydantic import Field, validator

from prefect.orion.utilities.enum import AutoEnum
from prefect.orion.utilities.functions import ParameterSchema
from prefect.orion.utilities.schemas import PrefectBaseModel


class APIBaseModel(PrefectBaseModel):
    class Config:
        orm_mode = True

    id: UUID = None
    created: datetime.datetime = None
    updated: datetime.datetime = None


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
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SCHEDULED = auto()
    PENDING = auto()


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


class _BaseState(PrefectBaseModel):
    type: StateType
    name: str = None
    timestamp: datetime.datetime = Field(default_factory=pendulum.now)
    message: str = Field(None, example="Run started")
    data: bytes = None

    @validator("name", pre=True, always=True)
    def default_name_from_type(cls, v, *, values, **kwargs):
        """If a name is not provided, use the type"""
        if v is None:
            v = values.get("type").value.capitalize()
        return v


class State(_BaseState, APIBaseModel):
    data_location: dict = None
    state_details: StateDetails = Field(default_factory=StateDetails)
    run_details: RunDetails = Field(default_factory=RunDetails)
