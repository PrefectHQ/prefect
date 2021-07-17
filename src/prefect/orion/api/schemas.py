import datetime
import json
from typing import Any, Dict, List, Union
from uuid import UUID

from pydantic import BaseModel, Field
from prefect.orion.api.schedules import IntervalSchedule


class APISchema(BaseModel):
    class Config:
        orm_mode = True

    id: UUID = None
    created: datetime.datetime = None
    updated: datetime.datetime = None


class Flow(APISchema):
    name: str
    tags: List[str] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)
