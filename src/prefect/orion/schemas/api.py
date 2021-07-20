"""
"Full" schemas for working with data objects internally
"""

import datetime
import json
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field

from prefect.orion.utilities.functions import ParameterSchema


class PrefectBaseModel(BaseModel):
    class Config:
        orm_mode = True

    id: UUID
    created: datetime.datetime
    updated: datetime.datetime

    def json_dict(self, *args, **kwargs) -> dict:
        """Returns a dict of JSON-compatible values, equivalent
        to `json.loads(self.json())`.

        `self.dict()` returns Python-native types, including UUIDs
        and datetimes; `self.json()` returns a JSON string. This
        method is useful when we require a JSON-compatible Python
        object.

        Returns:
            dict: a JSON-compatible dict
        """
        return json.loads(self.json(*args, **kwargs))


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
