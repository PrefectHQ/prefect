import datetime
import json
from enum import auto
from typing import Any, Dict, List, Union
from uuid import UUID

from pydantic import BaseModel, Field, validator

from prefect.orion.utilities.server import AutoEnum


class APISchema(BaseModel):
    class Config:
        orm_mode = True

    id: UUID = None


class ParameterType(AutoEnum):
    INT = auto()
    STRING = auto()
    FLOAT = auto()
    BOOLEAN = auto()
    JSON = auto()
    DATETIME = auto()


class Parameter(BaseModel):
    name: str
    type: ParameterType = ParameterType.JSON
    is_required: bool = False
    default: Any = None
    description: str = None

    @validator("default")
    def default_is_json(cls, v):
        try:
            json.dumps(v)
        except:
            raise ValueError("Default values must be JSON-compatible.")


class Flow(APISchema):
    name: str
    tags: List[str] = Field(default_factory=list)
    parameters: List[Parameter] = Field(default_factory=list)
