import uuid
from typing import List
from pydantic import Field, BaseModel


class Flow(BaseModel):
    class Config:
        orm_mode = True

    id: uuid.UUID = None
    name: str
    tags: List[str] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)
