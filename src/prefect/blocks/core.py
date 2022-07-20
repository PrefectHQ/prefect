import hashlib
import inspect
import logging
from abc import ABC
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, List, Optional, Type, Union
from uuid import UUID, uuid4

from griffe.dataclasses import Docstring, DocstringSection
from griffe.docstrings.dataclasses import DocstringSectionKind
from griffe.docstrings.parsers import Parser, parse
from pydantic import BaseModel, HttpUrl, SecretBytes, SecretStr
from typing_extensions import Self, get_args, get_origin

import prefect
from prefect.orion.schemas.core import BlockDocument, BlockSchema, BlockType
from prefect.utilities.asyncutils import asyncnullcontext, sync_compatible
from prefect.utilities.collections import remove_nested_keys
from prefect.utilities.dispatch import lookup_type, register_base_type
from prefect.utilities.hashing import hash_objects

if TYPE_CHECKING:
    from prefect.client import OrionClient


def block_schema_to_key(schema: BlockSchema) -> str:
    """
    Defines the unique key used to lookup the Block class for a given schema.
    """
    return f"{schema.block_type.name}:{schema.checksum}"


@register_base_type
class Block(BaseModel, ABC):
    class Config:
        extra = "allow"

        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: Type["Block"]):
            """
            Customizes Pydantic's schema generation feature to add blocks related information.
            """
            schema["block_type_name"] = model.get_block_type_name()
            # Ensures args and code examples aren't included in the schema
            description = model.get_description()
            if description:
                schema["description"] = model.get_description()

            # create a list of secret field names
            # secret fields include both top-level keys and dot-delimited nested secret keys
            # for example: ["x", "y", "child.a"]
            # means the top-level keys "x" and "y" are secret, as is the key "a" of a block
            # nested under the "child" key. There is no limit to nesting.
            secrets = schema["secret_fields"] = []
            for field in model.__fields__.values():
                if field.type_ in [SecretStr, SecretBytes]:
                    secrets.append(field.name)
                elif Block.is_block_class(field.type_):
                    secrets.extend(
                        f"{field.name}.{s}"
                        for s in field.type_.schema()["secret_fields"]
                    )

            # create block schema references
            refs = schema["block_schema_references"] = {}
            for field in model.__fields__.values():
                if Block.is_block_class(field.type_):
                    refs[field.name] = field.type_._to_block_schema_reference_dict()
                if get_origin(field.type_) is Union:
                    refs[field.name] = []
                    for type_ in get_args(field.type_):
                        if Block.is_block_class(type_):
                            refs[field.name].append(
                                type_._to_block_schema_reference_dict()
                            )

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

    # Attribute to customize the name of the block type created
    # when the block is registered with Orion. If not set, block
    # type name will default to the class name.
    _block_type_name: Optional[str] = None
    # Attributes used to set properties on a block type when registered
    # with Orion.
    _logo_url: Optional[HttpUrl] = None
    _documentation_url: Optional[HttpUrl] = None
    _description: Optional[str] = None
    _code_example: Optional[str] = None

    # -- private instance variables
    # these are set when blocks are loaded from the API
    _block_type_id: Optional[UUID] = None
    _block_schema_id: Optional[UUID] = None
    _block_schema_capabilities: Optional[List[str]] = None
    _block_document_id: Optional[UUID] = None
    _block_document_name: Optional[str] = None
    _is_anonymous: Optional[bool] = None

    @classmethod
    def __dispatch_key__(cls):
        if cls.__name__ == "Block":
            return None  # The base class is abstract
        return block_schema_to_key(cls._to_block_schema())

    @classmethod
    def get_block_type_name(cls):
        return cls._block_type_name or cls.__name__

    @classmethod
    def get_block_capabilities(cls) -> FrozenSet[str]:
        """
        Returns the block capabilities for this Block. Recursively collects all block
        capabilities of all parent classes into a single frozenset.
        """
        return frozenset(
            {
                c
                for base in (cls,) + cls.__mro__
                for c in getattr(base, "_block_schema_capabilities", []) or []
            }
        )

    @classmethod
    def _to_block_schema_reference_dict(cls):
        return dict(
            block_type_name=cls.get_block_type_name(),
            block_schema_checksum=cls._calculate_schema_checksum(),
        )

    @classmethod
    def _calculate_schema_checksum(
        cls, block_schema_fields: Optional[Dict[str, Any]] = None
    ):
        """
        Generates a unique hash for the underlying schema of block.

        Args:
            block_schema_fields: Dictionary detailing block schema fields to generate a
                checksum for. The fields of the current class is used if this parameter
                is not provided.

        Returns:
            str: The calculated checksum prefixed with the hashing algorithm used.
        """
        block_schema_fields = (
            cls.schema() if block_schema_fields is None else block_schema_fields
        )
        fields_for_checksum = remove_nested_keys(
            ["description", "definitions", "secret_fields"], block_schema_fields
        )
        checksum = hash_objects(fields_for_checksum, hash_algo=hashlib.sha256)
        if checksum is None:
            raise ValueError("Unable to compute checksum for block schema")
        else:
            return f"sha256:{checksum}"

    def _to_block_document(
        self,
        name: Optional[str] = None,
        block_schema_id: Optional[UUID] = None,
        block_type_id: Optional[UUID] = None,
        is_anonymous: Optional[bool] = None,
    ) -> BlockDocument:
        """
        Creates the corresponding block document based on the data stored in a block.
        The corresponding block document name, block type ID, and block schema ID must
        either be passed into the method or configured on the block.

        Args:
            name: The name of the created block document. Not required if anonymous.
            block_schema_id: UUID of the corresponding block schema.
            block_type_id: UUID of the corresponding block type.
            is_anonymous: if True, an anonymous block is created. Anonymous
                blocks are not displayed in the UI and used primarily for system
                operations and features that need to automatically generate blocks.

        Returns:
            BlockDocument: Corresponding block document
                populated with the block's configured data.
        """
        if is_anonymous is None:
            is_anonymous = self._is_anonymous or False

        # name must be present if not anonymous
        if not is_anonymous and not name and not self._block_document_name:
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
        block_document_data = self.dict(include=data_keys)

        # Iterate through and find blocks that already have saved block documents to
        # create references to those saved block documents.
        for key in data_keys:
            field_value = getattr(self, key)
            if (
                isinstance(field_value, Block)
                and field_value._block_document_id is not None
            ):
                block_document_data[key] = {
                    "$ref": {"block_document_id": field_value._block_document_id}
                }

        return BlockDocument(
            id=self._block_document_id or uuid4(),
            name=(name or self._block_document_name) if not is_anonymous else None,
            block_schema_id=block_schema_id or self._block_schema_id,
            block_type_id=block_type_id or self._block_type_id,
            data=block_document_data,
            block_schema=self._to_block_schema(
                block_type_id=block_type_id or self._block_type_id,
            ),
            block_type=self._to_block_type(),
            is_anonymous=is_anonymous,
        )

    @classmethod
    def _to_block_schema(cls, block_type_id: Optional[UUID] = None) -> BlockSchema:
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
            id=cls._block_schema_id if cls._block_schema_id is not None else uuid4(),
            checksum=cls._calculate_schema_checksum(),
            fields=fields,
            block_type_id=block_type_id or cls._block_type_id,
            block_type=cls._to_block_type(),
            capabilities=list(cls.get_block_capabilities()),
        )

    @classmethod
    def _parse_docstring(cls) -> List[DocstringSection]:
        """
        Parses the docstring into list of DocstringSection objects.
        Helper method used primarily to suppress irrelevant logs, e.g.
        `<module>:11: No type or annotation for parameter 'write_json'`
        because griffe is unable to parse the types from pydantic.BaseModel.
        """
        griffe_logger = logging.getLogger("griffe.docstrings.google")
        griffe_logger.disabled = True
        docstring = Docstring(cls.__doc__)
        parsed = parse(docstring, Parser.google)
        griffe_logger.disabled = False
        return parsed

    @classmethod
    def get_description(cls) -> Optional[str]:
        """
        Returns the description for the current block. Attempts to parse
        description from class docstring if an override is not defined.
        """
        description = cls._description
        # If no description override has been provided, find the first text section
        # and use that as the description
        if description is None and cls.__doc__ is not None:
            parsed = cls._parse_docstring()
            parsed_description = next(
                (
                    section.as_dict().get("value")
                    for section in parsed
                    if section.kind == DocstringSectionKind.text
                ),
                None,
            )
            if isinstance(parsed_description, str):
                description = parsed_description.strip()
        return description

    @classmethod
    def get_code_example(cls) -> Optional[str]:
        """
        Returns the code example for the given block. Attempts to parse
        code example from the class docstring if an override is not provided.
        """
        code_example = (
            dedent(cls._code_example) if cls._code_example is not None else None
        )
        # If no code example override has been provided, attempt to find a examples
        # section or an admonition with the annotation "example" and use that as the
        # code example
        if code_example is None and cls.__doc__ is not None:
            parsed = cls._parse_docstring()
            for section in parsed:
                # Section kind will be "examples" if Examples section heading is used.
                if section.kind == DocstringSectionKind.examples:
                    # Examples sections are made up of smaller sections that need to be
                    # joined with newlines. Smaller sections are represented as tuples
                    # with shape (DocstringSectionKind, str)
                    code_example = "\n".join(
                        (part[1] for part in section.as_dict().get("value", []))
                    )
                    break
                # Section kind will be "admonition" if Example section heading is used.
                if section.kind == DocstringSectionKind.admonition:
                    value = section.as_dict().get("value", {})
                    if value.get("annotation") == "example":
                        code_example = value.get("description")
                        break

        return code_example

    @classmethod
    def _to_block_type(cls) -> BlockType:
        """
        Creates the corresponding block type of the block.

        Returns:
            BlockType: The corresponding block type.
        """
        return BlockType(
            id=cls._block_type_id or uuid4(),
            name=cls.get_block_type_name(),
            logo_url=cls._logo_url,
            documentation_url=cls._documentation_url,
            description=cls.get_description(),
            code_example=cls.get_code_example(),
        )

    @classmethod
    def _from_block_document(cls, block_document: BlockDocument):
        """
        Instantiates a block from a given block document. The corresponding block class
        will be looked up in the block registry based on the corresponding block schema
        of the provided block document.

        Args:
            block_document: The block document used to instantiate a block.

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

        block_cls = (
            cls
            if cls.__name__ != "Block"
            # Look up the block class by dispatch
            else cls.get_block_class_from_schema(block_document.block_schema)
        )

        block = block_cls.parse_obj(block_document.data)
        block._block_document_id = block_document.id
        block.__class__._block_schema_id = block_document.block_schema_id
        block.__class__._block_type_id = block_document.block_type_id
        block._block_document_name = block_document.name
        block._is_anonymous = block_document.is_anonymous
        block._define_metadata_on_nested_blocks(
            block_document.block_document_references
        )

        return block

    @classmethod
    def get_block_class_from_schema(cls: Type[Self], schema: BlockSchema) -> Type[Self]:
        """
        Retieve the block class implementation given a schema.
        """
        return lookup_type(cls, block_schema_to_key(schema))

    def _define_metadata_on_nested_blocks(
        self, block_document_references: Dict[str, Dict[str, Any]]
    ):
        """
        Recursively populates metadata fields on nested blocks based on the
        provided block document references.
        """
        for item in block_document_references.items():
            field_name, block_document_reference = item
            nested_block = getattr(self, field_name)
            if isinstance(nested_block, Block):
                nested_block_document_info = block_document_reference.get(
                    "block_document", {}
                )
                nested_block._define_metadata_on_nested_blocks(
                    nested_block_document_info.get("block_document_references", {})
                )
                nested_block_document_id = nested_block_document_info.get("id")
                nested_block._block_document_id = (
                    UUID(nested_block_document_id) if nested_block_document_id else None
                )
                nested_block._block_document_name = nested_block_document_info.get(
                    "name"
                )
                nested_block._is_anonymous = nested_block_document_info.get(
                    "is_anonymous"
                )

    @classmethod
    @sync_compatible
    async def load(cls, name: str):
        """
        Retrieves data from the block document with the given name for the block type
        that corresponds with the current class and returns an instantiated version of
        the current class with the data stored in the block document.

        Args:
            name: The name of the block document.

        Raises:
            ValueError: If the requested block document is not found.

        Returns:
            An instance of the current class hydrated with the data stored in the
            block document with the specified name.
        """
        async with prefect.client.get_client() as client:
            try:
                block_document = await client.read_block_document_by_name(
                    name=name, block_type_name=cls.get_block_type_name()
                )
            except prefect.exceptions.ObjectNotFound as e:
                raise ValueError(
                    f"Unable to find block document named {name} for block type {cls.get_block_type_name()}"
                ) from e
        return cls._from_block_document(block_document)

    @staticmethod
    def is_block_class(block) -> bool:
        return inspect.isclass(block) and issubclass(block, Block)

    @classmethod
    async def register_type_and_schema(cls, client: Optional["OrionClient"] = None):
        """
        Makes block available for configuration with current Orion server.
        Recursively registers all nested blocks. Registration is idempotent.

        Args:
            client: Optional Orion client to use for registering type and schema with
                Orion. A new client will be created and used if one is not provided.
        """
        if cls.__name__ == "Block":
            raise ValueError(
                "`register_type_and_schema` should be called on a Block "
                "class and not on the Block class directly."
            )

        # Open a new client if one hasn't been provided. Otherwise,
        # use the provided client
        if client is None:
            client_context = prefect.client.get_client()
        else:
            client_context = asyncnullcontext()

        async with client_context as client_from_context:
            client = client or client_from_context
            for field in cls.__fields__.values():
                if Block.is_block_class(field.type_):
                    await field.type_.register_type_and_schema(client=client)
                if get_origin(field.type_) is Union:
                    for type_ in get_args(field.type_):
                        if Block.is_block_class(type_):
                            await type_.register_type_and_schema(client=client)

            try:
                block_type = await client.read_block_type_by_name(
                    name=cls.get_block_type_name()
                )
            except prefect.exceptions.ObjectNotFound:
                block_type = await client.create_block_type(
                    block_type=cls._to_block_type()
                )

            cls._block_type_id = block_type.id

            try:
                block_schema = await client.read_block_schema_by_checksum(
                    checksum=cls._calculate_schema_checksum()
                )
            except prefect.exceptions.ObjectNotFound:
                block_schema = await client.create_block_schema(
                    block_schema=cls._to_block_schema(block_type_id=block_type.id)
                )

            cls._block_schema_id = block_schema.id

    async def _save(
        self,
        name: Optional[str] = None,
        is_anonymous: bool = False,
        overwrite: bool = False,
    ):
        """
        Saves the values of a block as a block document with an option to save as an
        anonymous block document.

        Args:
            name: User specified name to give saved block document which can later be used to load the
                block document.
            is_anonymous: Boolean value specifying whether the block document is anonymous. Anonymous
                blocks are intended for system use and are not shown in the UI. Anonymous blocks do not
                require a user-supplied name.
            overwrite: Boolean value specifying if values should be overwritten if a block document with
                the specified name already exists.

        Raises:
            ValueError: If a name is not given and `is_anonymous` is `False` or a name is given and
                `is_anonymous` is `True`.
        """
        if name is None and not is_anonymous:
            raise ValueError(
                "You're attempting to save a block document without a name. "
                "Please either save a block document with a name or set "
                "is_anonymous to True."
            )

        self._is_anonymous = is_anonymous
        async with prefect.client.get_client() as client:

            # Ensure block type and schema are registered before saving block document.
            await self.register_type_and_schema(client=client)

            try:
                block_document = await client.create_block_document(
                    block_document=self._to_block_document(name=name)
                )
            except prefect.exceptions.ObjectAlreadyExists as err:
                if overwrite:
                    block_document_id = self._block_document_id
                    if block_document_id is None:
                        existing_block_document = (
                            await client.read_block_document_by_name(
                                name=name, block_type_name=self.get_block_type_name()
                            )
                        )
                        block_document_id = existing_block_document.id
                    await client.update_block_document(
                        block_document_id=block_document_id,
                        block_document=self._to_block_document(name=name),
                    )
                    block_document = await client.read_block_document(
                        block_document_id=block_document_id
                    )
                else:
                    raise ValueError(
                        "You are attempting to save values with a name that is already in "
                        "use for this block type. If you would like to overwrite the values that are saved, "
                        "then save with `overwrite=True`."
                    ) from err

        # Update metadata on block instance for later use.
        self._block_document_name = block_document.name
        self._block_document_id = block_document.id
        return self._block_document_id

    @sync_compatible
    async def save(self, name: str, overwrite: bool = False):
        """
        Saves the values of a block as a block document.

        Args:
            name: User specified name to give saved block document which can later be used to load the
                block document.
            overwrite: Boolean value specifying if values should be overwritten if a block document with
                the specified name already exists.

        """
        document_id = await self._save(name=name, overwrite=overwrite)

        return document_id
