import datetime
from typing import List, Dict
from uuid import UUID

from pydantic import Field

from prefect.orion.utilities.functions import ParameterSchema
from prefect.orion.utilities.schemas import PrefectBaseModel, ORMBaseModel


class Flow(ORMBaseModel):
    name: str = Field(..., example="my-flow")
    tags: List[str] = Field(default_factory=list, example=["tag-1", "tag-2"])
    parameters: ParameterSchema = Field(default_factory=ParameterSchema)


class FlowRunDetails(PrefectBaseModel):
    pass


class FlowRun(ORMBaseModel):
    flow_id: UUID
    deployment_id: UUID = None
    flow_version: str = Field(None, example="1.0")
    parameters: dict = Field(default_factory=dict)
    idempotency_key: str = None
    context: dict = Field(default_factory=dict, example={"my_var": "my_val"})
    empirical_policy: dict = Field(default_factory=dict)
    empirical_config: dict = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list, example=["tag-1", "tag-2"])
    flow_run_details: FlowRunDetails = Field(default_factory=FlowRunDetails)
    parent_task_run_id: UUID = None


class TaskRunDetails(PrefectBaseModel):
    pass


class TaskRunPolicy(PrefectBaseModel):
    max_retries: int = 0
    retry_delay_seconds: float = 0


class TaskRun(ORMBaseModel):
    flow_run_id: UUID
    task_key: str
    dynamic_key: str = None
    cache_key: str = None
    cache_expiration: datetime.datetime = None
    task_version: str = None
    empirical_policy: TaskRunPolicy = Field(default_factory=TaskRunPolicy)
    tags: List[str] = Field(default_factory=list, example=["tag-1", "tag-2"])
    task_inputs: ParameterSchema = Field(default_factory=ParameterSchema)
    upstream_task_run_ids: Dict[str, UUID] = Field(default_factory=dict)
    task_run_details: TaskRunDetails = Field(default_factory=TaskRunDetails)


class Deployment(ORMBaseModel):
    name: str
    flow_id: UUID
