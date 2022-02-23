from uuid import UUID
from abc import ABC, abstractmethod
from typing import Dict, Optional

from pydantic import BaseModel
import prefect

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
    A base class for implementing a generic interface that references an Orion
    Block.

    This class can be defined with an arbitrary set of fields and methods, and
    couples business logic with data contained in an Orion Block. `block_name`,
    `block_id` and `block_spec_id` are reserved by Orion as Block metadata
    fields, but otherwise a Block can implement arbitrary logic. Blocks can be
    instantiated without populating these metadata fields, but can only be used
    interactively, not with the Orion API.

    Instead of the __init__ method, a Block implementation requires the
    definition of a `block_initialization` method that is called after
    initialization.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.block_initialization()

    @abstractmethod
    def block_initialization(self) -> None:
        pass

    block_spec_id: Optional[UUID]
    block_id: Optional[UUID]
    block_name: Optional[str]

    @staticmethod
    def from_api_block(api_block: prefect.orion.schemas.core.Block):
        block_spec_cls = get_block_spec(
            name=api_block.block_spec.name, version=api_block.block_spec.version
        )
        return block_spec_cls(
            block_id=api_block.id,
            block_spec_id=api_block.block_spec_id,
            block_name=api_block.name,
            **api_block.data
        )

    def to_api_block(self) -> prefect.orion.schemas.core.Block:
        data = self.dict()

        for field in ["block_spec_id", "block_id", "block_name"]:
            data.pop(field)

        return prefect.orion.schemas.core.Block(
            id=self.block_id,
            name=self.block_name,
            block_spec_id=self.block_spec_id,
            data=data,
        )
