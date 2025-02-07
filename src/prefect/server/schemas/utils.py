from pydantic import BaseModel


class DynamicObject(BaseModel):
    class Config:
        extra = "allow"
