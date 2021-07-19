import uuid
from typing import List
from pydantic import Field, BaseModel


class PrefectBaseModel(BaseModel):
    class Config:
        orm_mode = True

    id: uuid.UUID = None


class Flow(PrefectBaseModel):
    name: str
    tags: List[str] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)


class FlowRun(PrefectBaseModel):
    flow_id: uuid.UUID
    flow_version: str
    parameters: dict = Field(default_factory=dict)
    parent_task_run_id: uuid.UUID = None
    context: dict = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
