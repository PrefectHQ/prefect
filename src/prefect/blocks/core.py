import datetime
from functools import wraps
from typing import Dict
from abc import ABC, abstractmethod

from pydantic import BaseModel, parse_obj_as

BLOCK_API_REGISTRY: Dict[str, "BlockAPI"] = dict()


def register_blockapi(blockref):
    def wrapper(blockapi):
        BLOCK_API_REGISTRY[blockref] = blockapi
        return blockapi

    return wrapper


def get_blockapi(blockref):
    from prefect.blocks import storage

    return BLOCK_API_REGISTRY.get(blockref)


class BlockAPI(BaseModel, ABC):
    class Config:
        extra = "allow"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.block_initialization()

    @abstractmethod
    def block_initialization(self) -> None:
        pass

    blockname: str
    blockref: str
    blockid: str
