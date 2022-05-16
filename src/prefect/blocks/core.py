import hashlib
import json
from abc import ABC
from multiprocessing.sharedctypes import Value
from typing import Dict, Optional, Type
from uuid import UUID, uuid4

from pydantic import BaseModel, HttpUrl

import prefect
from prefect.orion.schemas.core import BlockDocument, BlockSchema, BlockType
from prefect.utilities.hashing import hash_objects

BLOCK_REGISTRY: Dict[str, Type["Block"]] = dict()


def register_block(block: Type["Block"]):
    """
    Register a block class for later use. Blocks can be retrieved via
    block schema checksum.
    """
    schema_checksum = block.calculate_schema_checksum()
    BLOCK_REGISTRY[schema_checksum] = block
    return block


def get_block_class(checksum: str) -> Type["Block"]:
    block = BLOCK_REGISTRY.get(checksum)
    if not block:
        raise ValueError(
            f"No block schema exists for block schema checksum {checksum}."
        )
    return block


class Block(BaseModel, ABC):
    class Config:
        extra = "allow"

    """
    A base class for implementing a block that wraps an external service.

    This class can be defined with an arbitrary set of fields and methods, and
    couples business logic with data contained in an block document. 
    `_block_document_name`, `_block_document_id`, `_block_schema_id`, and 
    `_block_type_id` are reserved by Orion as Block metadata fields, but 
    otherwise a Block can implement arbitrary logic. Blocks can be instantiated
    without populating these metadata fields, but can only be used interactively,
    not with the Orion API.

    Instead of the __init__ method, a block implementation allows the
    definition of a `block_initialization` method that is called after
    initialization.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.block_initialization()

    def block_initialization(self) -> None:
        pass

    # -- private class variables
    # set by the class itself
    _block_schema_type: Optional[str] = None
    # Attribute to customize the name of the block type created
    # when the block is registered with Orion. If not set, block
    # type name will default to the class name.
    _block_type_name: Optional[str] = None
    # Attributes used to set properties on a block type when registered
    # with Orion.
    _logo_url: Optional[HttpUrl] = None
    _documentation_url: Optional[HttpUrl] = None

    # -- private instance variables
    # these are set when blocks are loaded from the API
    _block_type_id: Optional[UUID] = None
    _block_schema_id: Optional[UUID] = None
    _block_document_id: Optional[UUID] = None
    _block_document_name: Optional[str] = None

    @classmethod
    def calculate_schema_checksum(cls):
        """
        Generates a unique hash for the underlying schema of block.
        """
        checksum = hash_objects(cls.schema(), hash_algo=hashlib.sha256)
        if checksum is None:
            raise ValueError("Unable to compute checksum for block schema")
        else:
            return f"sha256:{checksum}"

    def to_block_document(
        self,
        name: Optional[str] = None,
        block_schema_id: Optional[UUID] = None,
        block_type_id: Optional[UUID] = None,
    ) -> BlockDocument:
        """
        Creates the corresponding block document based on the data stored in a block.
        The corresponding block document name, block type ID, and block schema ID must
        either be passed into the method or configured on the block.

        Args:
            name: The name of the created block document.
            block_schema_id: UUID of the corresponding block schema.
            block_type_id: UUID of the corresponding block type.

        Returns:
            BlockDocument: Corresponding block document
                populated with the block's configured data.
        """
        if not name and not self._block_document_name:
            raise ValueError("No name provided, either as an argument or on the block.")
        if not block_schema_id and not self._block_schema_id:
            raise ValueError(
                "No block schema ID provided, either as an argument or on the block."
            )
        if not block_type_id and not self._block_type_id:
            raise ValueError(
                "No block type ID provided, either as an argument or on the block."
            )

        data_keys = self.schema()["properties"].keys()
        return BlockDocument(
            id=self._block_document_id or uuid4(),
            name=name or self._block_document_name,
            block_schema_id=block_schema_id or self._block_schema_id,
            block_type_id=block_type_id or self._block_type_id,
            data=self.dict(include=data_keys),
            block_schema=self.to_block_schema(
                block_type_id=block_type_id or self._block_type_id,
            ),
            block_type=self.to_block_type(),
        )

    @classmethod
    def to_block_schema(cls, block_type_id: Optional[UUID] = None) -> BlockSchema:
        """
        Creates the corresponding block schema of the block.
        The corresponding block_type_id must either be passed into
        the method or configured on the block.

        Args:
            block_type_id: UUID of the corresponding block type.

        Returns:
            BlockSchema: The corresponding block schema.
        """
        fields = cls.schema()
        return BlockSchema(
            id=cls._block_schema_id or uuid4(),
            checksum=cls.calculate_schema_checksum(),
            type=cls._block_schema_type,
            fields=fields,
            block_type_id=block_type_id or cls._block_type_id,
            block_type=cls.to_block_type(),
        )

    @classmethod
    def to_block_type(cls) -> BlockType:
        """
        Creates the corresponding block type of the block.

        Returns:
            BlockType: The corresponding block type.
        """
        return BlockType(
            id=cls._block_type_id or uuid4(),
            name=cls._block_type_name or cls.__name__,
            logo_url=cls._logo_url,
            documentation_url=cls._documentation_url,
        )

    @classmethod
    def from_block_document(cls, block_document: BlockDocument):
        """
        Instantiates a block from a given block document. The corresponding block class
        will be looked up in the block registry based on the corresponding block schema
        of the provided block document.

        Raises:
            ValueError: If the provided block document doesn't have a corresponding block
                schema.

        Returns:
            Block: Hydrated block with data from block document.
        """
        if block_document.block_schema is None:
            raise ValueError(
                "Unable to determine block schema for provided block document"
            )
        block_schema_cls = (
            cls
            if cls.__name__ != "Block"
            else get_block_class(
                checksum=block_document.block_schema.checksum,
            )
        )
        block = block_schema_cls(**block_document.data)
        block._block_document_id = block_document.id
        block._block_schema_id = block_document.block_schema_id
        block._block_type_id = block_document.block_type_id
        block._block_document_name = block_document.name
        return block

    @classmethod
    async def from_name(cls, name: str):
        async with prefect.client.get_client() as client:
            block_type_name = cls._block_type_name or cls.__name__
            try:
                block_document = await client.read_block_document_by_name(
                    name=name, block_type_name=block_type_name
                )
            except prefect.exceptions.ObjectNotFound as e:
                raise ValueError(
                    f"Unable to find block document named {name} for block type {cls._block_type_name or cls.__name__}"
                )
        return cls.from_block_document(block_document)
