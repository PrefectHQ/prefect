from abc import ABC
from typing import Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel

import prefect
from prefect.orion.utilities.functions import parameter_schema

BLOCK_REGISTRY: Dict[str, "Block"] = dict()


def register_block(name: str = None, version: str = None):
    """
    Register a block schema with an optional name and version.

    Args:
        name (str): If provided, the block schema name. If not provided, the
            `_block_schema_name` private field will be checked, and if that is
            `None`, the block schema class name will be used.
        version (str): If provided, the block schema version. If not provided,
            the `_block_schema_version` private field will be checked. If not
            found, an error will be raised.
    """

    def wrapper(block):
        registered_name = name or block._block_schema_name
        if not registered_name:
            raise ValueError("No _block_schema_name set and no name provided.")
        registered_version = version or block._block_schema_version
        if not registered_version:
            raise ValueError("No _block_schema_version set and no version provided.")

        BLOCK_REGISTRY[(registered_name, registered_version)] = block
        block._block_schema_name = registered_name
        block._block_schema_version = registered_version
        return block

    return wrapper


def get_block_class(name: str, version: str) -> "Block":
    block = BLOCK_REGISTRY.get((name, version))
    if not block:
        raise ValueError(f"No block schema exists for {name}/{version}.")
    return block


class Block(BaseModel, ABC):
    class Config:
        extra = "allow"

    """
    A base class for implementing a generic interface that references an Orion
    Block.

    This class can be defined with an arbitrary set of fields and methods, and
    couples business logic with data contained in an Orion Block. `block_name`,
    `block_document_id`, `block_schema_id`, `block_schema_name`, and 
    `block_schema_version` are reserved by Orion as Block metadata fields, but 
    otherwise a Block can implement arbitrary logic. Blocks can be instantiated
    without populating these metadata fields, but can only be used interactively,
    not with the Orion API.

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
    _block_schema_type: Optional[str] = None
    # name and version are set by the registration decorator
    _block_schema_name: Optional[str] = None
    _block_schema_version: Optional[str] = None

    # -- private instance variables
    # these are set when blocks are loaded from the API
    _block_document_id: Optional[UUID] = None
    _block_schema_id: Optional[UUID] = None
    _block_document_name: Optional[str] = None

    def to_block_document(
        self, name: str = None, block_schema_id: UUID = None
    ) -> prefect.orion.schemas.core.BlockDocument:
        if not name or self._block_document_name:
            raise ValueError("No name provided, either as an argument or on the block.")
        if not block_schema_id or self._block_schema_id:
            raise ValueError(
                "No block schema ID provided, either as an argument or on the block."
            )

        data_keys = self.schema()["properties"].keys()
        return prefect.orion.schemas.core.BlockDocument(
            id=self._block_document_id or uuid4(),
            name=name or self._block_document_name,
            block_schema_id=block_schema_id or self._block_schema_id,
            data=self.dict(include=data_keys),
            block_schema=self.to_block_schema(),
        )

    @classmethod
    def to_block_schema(cls) -> prefect.orion.schemas.core.BlockSchema:
        fields = cls.schema()
        fields["title"] = cls._block_schema_name
        return prefect.orion.schemas.core.BlockSchema(
            name=cls._block_schema_name,
            version=cls._block_schema_version,
            type=cls._block_schema_type,
            fields=fields,
        )


def create_block_from_block_document(block_document_dict: dict):
    block_document = prefect.orion.schemas.core.BlockDocument.parse_obj(
        block_document_dict
    )
    block_schema_cls = get_block_class(
        name=block_document.block_schema.name,
        version=block_document.block_schema.version,
    )
    block = block_schema_cls(**block_document.data)
    block._block_document_id = block_document.id
    block._block_schema_id = block_document.block_schema_id
    block._block_name = block_document.name
    return block
