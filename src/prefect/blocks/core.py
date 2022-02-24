from abc import ABC, abstractmethod
from typing import ClassVar, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, root_validator

import prefect
from prefect.orion.utilities.functions import parameter_schema

BLOCK_REGISTRY: Dict[str, "Block"] = dict()


def register_block(name: str, version: str):
    def wrapper(block):
        BLOCK_REGISTRY[(name, version)] = block
        block._block_spec_name = name
        block._block_spec_version = version
        return block

    return wrapper


def get_block_spec(name: str, version: str) -> "Block":
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

    Instead of the __init__ method, a Block implementation allows the
    definition of a `block_initialization` method that is called after
    initialization.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.block_initialization()

    def block_initialization(self) -> None:
        pass

    # -- private class variables
    # type is set by the class itself
    _block_spec_type: Optional[str] = None
    # name and version are set by the registration decorator
    _block_spec_name: Optional[str] = None
    _block_spec_version: Optional[str] = None

    # -- private instance variables
    # these are set when blocks are loaded from the API
    _block_id: Optional[UUID] = None
    _block_spec_id: Optional[UUID] = None
    _block_name: Optional[str] = None

    @root_validator(pre=True)
    def set_private_variables(cls, values):
        return values

    def to_api_block(self, name: str = None) -> prefect.orion.schemas.core.Block:
        if not name or self._block_name:
            raise ValueError("No name provided.")
        return prefect.orion.schemas.core.Block(
            id=self._block_id,
            name=name or self._block_name,
            block_spec_id=self._block_spec_id,
            data=self.dict(),
        )

    @classmethod
    def to_api_block_spec(cls) -> prefect.orion.schemas.core.BlockSpec:
        fields = cls.schema()
        return prefect.orion.schemas.core.BlockSpec(
            name=cls._block_spec_name,
            version=cls._block_spec_version,
            type=cls._block_spec_type,
            fields=fields,
        )


def create_block_from_api_block(api_block_dict: dict):
    api_block = prefect.orion.schemas.core.Block.parse_obj(api_block_dict)
    block_spec_cls = get_block_spec(
        name=api_block.block_spec.name,
        version=api_block.block_spec.version,
    )
    block = block_spec_cls(**api_block.data)
    block._block_id = api_block.id
    block._block_spec_id = api_block.block_spec_id
    block._block_name = api_block.name
    return block
