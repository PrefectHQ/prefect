from abc import ABC
from typing import Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel

import prefect
from prefect.orion.utilities.functions import parameter_schema

BLOCK_REGISTRY: Dict[str, "Block"] = dict()


def register_block(name: str = None, version: str = None):
    """
    Register a block spec with an optional name and version.

    Args:
        name (str): If provided, the block spec name. If not provided, the
            `_block_spec_name` private field will be checked, and if that is
            `None`, the block spec class name will be used.
        version (str): If provided, the block spec version. If not provided,
            the `_block_spec_version` private field will be checked. If not
            found, an error will be raised.
    """

    def wrapper(block):
        registered_name = name or block._block_spec_name
        if not registered_name:
            raise ValueError("No _block_spec_name set and no name provided.")
        registered_version = version or block._block_spec_version
        if not registered_version:
            raise ValueError("No _block_spec_version set and no version provided.")

        BLOCK_REGISTRY[(registered_name, registered_version)] = block
        block._block_spec_name = registered_name
        block._block_spec_version = registered_version
        return block

    return wrapper


def get_block_class(name: str, version: str) -> "Block":
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

    def to_api_block(
        self, name: str = None, block_spec_id: UUID = None
    ) -> prefect.orion.schemas.core.Block:
        if not name or self._block_name:
            raise ValueError("No name provided, either as an argument or on the block.")
        if not block_spec_id or self._block_spec_id:
            raise ValueError(
                "No block spec ID provided, either as an argument or on the block."
            )

        data_keys = self.schema()["properties"].keys()
        return prefect.orion.schemas.core.Block(
            id=self._block_id or uuid4(),
            name=name or self._block_name,
            block_spec_id=block_spec_id or self._block_spec_id,
            data=self.dict(include=data_keys),
            block_spec=self.to_api_block_spec(),
        )

    @classmethod
    def to_api_block_spec(cls) -> prefect.orion.schemas.core.BlockSpec:
        fields = cls.schema()
        fields["title"] = cls._block_spec_name
        return prefect.orion.schemas.core.BlockSpec(
            name=cls._block_spec_name,
            version=cls._block_spec_version,
            type=cls._block_spec_type,
            fields=fields,
        )


def create_block_from_api_block(api_block_dict: dict):
    api_block = prefect.orion.schemas.core.Block.parse_obj(api_block_dict)
    block_spec_cls = get_block_class(
        name=api_block.block_spec.name,
        version=api_block.block_spec.version,
    )
    block = block_spec_cls(**api_block.data)
    block._block_id = api_block.id
    block._block_spec_id = api_block.block_spec_id
    block._block_name = api_block.name
    return block
