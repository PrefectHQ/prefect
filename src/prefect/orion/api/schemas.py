import json
import uuid
from typing import List
from pydantic import Field, BaseModel


class PrefectBaseModel(BaseModel):
    class Config:
        orm_mode = True

    id: uuid.UUID = None

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
    parameters: dict = Field(default_factory=dict)


class FlowRun(PrefectBaseModel):
    flow_id: uuid.UUID
    flow_version: str
    parameters: dict = Field(default_factory=dict)
    parent_task_run_id: uuid.UUID = None
    context: dict = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
