import datetime
from abc import ABC, abstractmethod
from functools import wraps
from typing import Dict, Optional

from pydantic import BaseModel, parse_obj_as

BLOCK_API_REGISTRY: Dict[str, "BlockAPI"] = dict()


def register_blockapi(blockref):
    def wrapper(blockapi):
        BLOCK_API_REGISTRY[blockref] = blockapi
        return blockapi

    return wrapper


def get_blockapi(blockref):
    return BLOCK_API_REGISTRY.get(blockref)


class BlockAPI(BaseModel, ABC):
    class Config:
        extra = "allow"

    """
    A base class for implementing a generic interface that references an Orion Block.

    This class can be defined with an arbitrary set of fields and methods, and couples
    business logic with data contained in an Orion Block. `blockname`, `blockref` and
    `blockid` are reserved by Orion as Block metadata fields, but otherwise a BlockAPI
    can implement arbitrary logic.

    Instead of the __init__ method, a BlockAPI implementation requires the definition of
    a `block_initialization` method that is called after initialization.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.block_initialization()

    @abstractmethod
    def block_initialization(self) -> None:
        pass

    blockref: str
    blockname: Optional[str]
    blockid: Optional[str]
