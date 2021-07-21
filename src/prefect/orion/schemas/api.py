"""
"Full" schemas for working with data objects internally
"""

import datetime
from typing import List, Dict
from uuid import UUID

from pydantic import Field

from prefect.orion.utilities.functions import ParameterSchema
from prefect.orion.utilities.schemas import PrefectBaseModel


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


class FlowRun(APIBaseModel):
    flow_id: UUID
    flow_version: str = Field(..., example="v1.0")
    parameters: dict = Field(default_factory=dict)
    parent_task_run_id: UUID = None
    context: dict = Field(default_factory=dict, example={"my_var": "my_val"})
    tags: List[str] = Field(default_factory=list, example=["tag-1", "tag-2"])


class TaskRunMetadata(PrefectBaseModel):
    is_subflow: bool = False


class TaskRun(APIBaseModel):
    flow_run_id: UUID
    task_key: str
    dynamic_key: str
    cache_key: str
    cache_expiration: datetime.datetime
    task_version: str
    empirical_policy: dict = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list, example=["tag-1", "tag-2"])
    inputs: ParameterSchema = Field(default_factory=ParameterSchema)
    upstream_task_run_ids: Dict[str, UUID] = Field(default_factory=dict)
    task_run_metadata: TaskRunMetadata = Field(default_factory=TaskRunMetadata)
