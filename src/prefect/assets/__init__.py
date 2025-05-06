from __future__ import annotations
from pydantic import BaseModel


class Resource(BaseModel):
    key: str

    __hash__ = object.__hash__  # type: ignore


class Asset(Resource):
    key: str
