import datetime
import json
from enum import auto
from typing import Any, Dict, List, Union
from uuid import UUID

from pydantic import BaseModel, Field, validator
from prefect.orion.utilities.functions import ParameterSchema


class PrefectBaseModel(BaseModel):
    class Config:
        orm_mode = True

    id: UUID = None


class Flow(PrefectBaseModel):
    name: str
    tags: List[str] = Field(default_factory=list)
    parameters: ParameterSchema = Field(default_factory=ParameterSchema)


class FlowRun(PrefectBaseModel):
    flow_id: UUID
    flow_version: str
    parameters: dict = Field(default_factory=dict)
    parent_task_run_id: UUID = None
    context: dict = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
