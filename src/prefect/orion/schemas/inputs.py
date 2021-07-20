"""
Reduced schemas for accepting API inputs
"""

from typing import List
from uuid import UUID

from pydantic import BaseModel, Field

from prefect.orion.utilities.functions import ParameterSchema


class FlowCreate(BaseModel):
    name: str
    tags: List[str] = Field(default_factory=list)
    parameters: ParameterSchema = Field(default_factory=ParameterSchema)


class FlowRunCreate(BaseModel):
    flow_id: UUID
    flow_version: str
    parameters: dict = Field(default_factory=dict)
    parent_task_run_id: UUID = None
    context: dict = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
