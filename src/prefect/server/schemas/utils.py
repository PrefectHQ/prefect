from pydantic import BaseModel, ConfigDict


class DynamicObject(BaseModel):
    model_config = ConfigDict(extra="allow")
