import datetime
from abc import ABC, abstractmethod
from functools import wraps
from typing import Dict, Optional

from pydantic import BaseModel, parse_obj_as

BLOCK_REGISTRY: Dict[str, "Block"] = dict()


def register_block(name: str, version: str = None):
    def wrapper(block):
        BLOCK_REGISTRY[(name, version)] = block
        return block

    return wrapper


def get_block_spec(name: str, version: str = None) -> "Block":
    return BLOCK_REGISTRY.get((name, version))


class Block(BaseModel, ABC):
    class Config:
        extra = "allow"

    """
    A base class for implementing a generic interface that references an Orion Block.

    This class can be defined with an arbitrary set of fields and methods, and couples
    business logic with data contained in an Orion Block. `blockname`, `blockref` and
    `blockid` are reserved by Orion as Block metadata fields, but otherwise a Block
    can implement arbitrary logic.

    Instead of the __init__ method, a Block implementation requires the definition of
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
