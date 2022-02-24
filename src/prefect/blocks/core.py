from abc import ABC, abstractmethod
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel

import prefect

BLOCK_REGISTRY: Dict[str, "Block"] = dict()


def register_block(name: str, version: str = None):
    def wrapper(block):
        BLOCK_REGISTRY[(name, version)] = block
        return block

    return wrapper


def get_block_spec(name: str, version: str = None) -> "Block":
    block = BLOCK_REGISTRY.get((name, version))
    if not block:
        raise ValueError(f"No block spec exists for {name}/{version}.")
    return block


class Block(BaseModel, ABC):
    class Config:
        extra = "allow"

    """
    A base class for implementing a generic interface that references an Orion
    Block.

    This class can be defined with an arbitrary set of fields and methods, and
    couples business logic with data contained in an Orion Block. `block_name`,
    `block_id`, `block_spec_id`, `block_spec_name`, and `block_spec_version` are
    reserved by Orion as Block metadata fields, but otherwise a Block can
    implement arbitrary logic. Blocks can be instantiated without populating
    these metadata fields, but can only be used interactively, not with the
    Orion API.

    Instead of the __init__ method, a Block implementation requires the
    definition of a `block_initialization` method that is called after
    initialization.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.block_initialization()

    def block_initialization(self) -> None:
        pass

    block_spec_id: Optional[UUID]
    block_spec_name: Optional[str]
    block_spec_version: Optional[str]
    block_id: Optional[UUID]
    block_name: Optional[str]

    @staticmethod
    def from_api_block(api_block_dict: dict):
        api_block = prefect.orion.schemas.core.Block.parse_obj(api_block_dict)
        block_spec_cls = get_block_spec(
            name=api_block.block_spec.name,
            version=api_block.block_spec.version,
        )
        return block_spec_cls(
            block_id=api_block.id,
            block_spec_id=api_block.block_spec_id,
            block_name=api_block.name,
            block_spec_name=api_block.block_spec.name,
            block_spec_version=api_block.block_spec.version,
            **api_block.data,
        )

    def to_api_block(self) -> prefect.orion.schemas.core.Block:
        data = self.dict()

        for field in [
            "block_spec_id",
            "block_id",
            "block_name",
            "block_spec_name",
            "block_spec_version",
        ]:
            data.pop(field)

        return prefect.orion.schemas.core.Block(
            id=self.block_id,
            name=self.block_name,
            block_spec_id=self.block_spec_id,
            data=data,
        )
