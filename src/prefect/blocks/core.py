import hashlib
import inspect
import logging
import sys
import warnings
from abc import ABC
from textwrap import dedent
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    FrozenSet,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
)
from uuid import UUID, uuid4

from griffe.dataclasses import Docstring
from griffe.docstrings.dataclasses import DocstringSection, DocstringSectionKind
from griffe.docstrings.parsers import Parser, parse
from pydantic import BaseModel, HttpUrl, SecretBytes, SecretStr
from slugify import slugify
from typing_extensions import ParamSpec, Self, get_args, get_origin

import prefect
from prefect.orion.schemas.core import (
    DEFAULT_BLOCK_SCHEMA_VERSION,
    BlockDocument,
    BlockSchema,
    BlockType,
)
from prefect.utilities.asyncutils import asyncnullcontext, sync_compatible
from prefect.utilities.collections import remove_nested_keys
from prefect.utilities.dispatch import lookup_type, register_base_type
from prefect.utilities.hashing import hash_objects
from prefect.utilities.importtools import to_qualified_name

if TYPE_CHECKING:
    from prefect.client import OrionClient

R = TypeVar("R")
P = ParamSpec("P")


def block_schema_to_key(schema: BlockSchema) -> str:
    """
    Defines the unique key used to lookup the Block class for a given schema.
    """
    return f"{schema.block_type.slug}"


class InvalidBlockRegistration(Exception):
    """
    Raised on attempted registration of the base Block
    class or a Block interface class
    """


def _collect_nested_reference_strings(obj: Dict):
    """
    Collects all nested reference strings (e.g. #/definitions/Model) from a given object.
    """
    found_reference_strings = []
    if isinstance(obj, dict):
        if obj.get("$ref"):
            found_reference_strings.append(obj.get("$ref"))
        for value in obj.values():
            found_reference_strings.extend(_collect_nested_reference_strings(value))
    if isinstance(obj, list):
        for item in obj:
            found_reference_strings.extend(_collect_nested_reference_strings(item))
    return found_reference_strings


def _get_non_block_reference_definitions(object_definition: Dict, definitions: Dict):
    """
    Given a definition of an object in a block schema OpenAPI spec and the dictionary
    of all reference definitions in that same block schema OpenAPI spec, return the
    definitions for objects that are referenced from the object or any children of
    the object that do not reference a block.
    """
    non_block_definitions = {}
    reference_strings = _collect_nested_reference_strings(object_definition)
    for reference_string in reference_strings:
        definition_key = reference_string.replace("#/definitions/", "")
        definition = definitions.get(definition_key)
        if definition and definition.get("block_type_slug") is None:
            non_block_definitions = {
                **non_block_definitions,
                definition_key: definition,
                **_get_non_block_reference_definitions(definition, definitions),
            }
    return non_block_definitions


@register_base_type
class Block(BaseModel, ABC):
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

    class Config:
        extra = "allow"

        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: Type["Block"]):
            """
            Customizes Pydantic's schema generation feature to add blocks related information.
            """
            schema["block_type_slug"] = model.get_block_type_slug()
            # Ensures args and code examples aren't included in the schema
            description = model.get_description()
            if description:
                schema["description"] = description
            else:
                # Prevent the description of the base class from being included in the schema
                schema.pop("description", None)

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
                    for type_ in get_args(field.type_):
                        if Block.is_block_class(type_):
                            if isinstance(refs.get(field.name), list):
                                refs[field.name].append(
                                    type_._to_block_schema_reference_dict()
                                )
                            elif isinstance(refs.get(field.name), dict):
                                refs[field.name] = [
                                    refs[field.name],
                                    type_._to_block_schema_reference_dict(),
                                ]
                            else:
                                refs[
                                    field.name
                                ] = type_._to_block_schema_reference_dict()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.block_initialization()

    def __str__(self) -> str:
        return self.__repr__()

    def __repr_args__(self):
        repr_args = super().__repr_args__()
        data_keys = self.schema()["properties"].keys()
        return [
            (key, value) for key, value in repr_args if key is None or key in data_keys
        ]

    def block_initialization(self) -> None:
        pass

    # -- private class variables
    # set by the class itself

    # Attribute to customize the name of the block type created
    # when the block is registered with Orion. If not set, block
    # type name will default to the class name.
    _block_type_name: Optional[str] = None
    _block_type_slug: Optional[str] = None

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
    _block_schema_version: Optional[str] = None
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
    def get_block_type_slug(cls):
        return slugify(cls._block_type_slug or cls.get_block_type_name())

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
    def _get_current_package_version(cls):
        current_module = inspect.getmodule(cls)
        if current_module:
            top_level_module = sys.modules[
                current_module.__name__.split(".")[0] or "__main__"
            ]
            try:
                return str(top_level_module.__version__)
            except AttributeError:
                # Module does not have a __version__ attribute
                pass
        return DEFAULT_BLOCK_SCHEMA_VERSION

    @classmethod
    def get_block_schema_version(cls) -> str:
        return cls._block_schema_version or cls._get_current_package_version()

    @classmethod
    def _to_block_schema_reference_dict(cls):
        return dict(
            block_type_slug=cls.get_block_type_slug(),
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
        fields_for_checksum = remove_nested_keys(["secret_fields"], block_schema_fields)
        if fields_for_checksum.get("definitions"):
            non_block_definitions = _get_non_block_reference_definitions(
                fields_for_checksum, fields_for_checksum["definitions"]
            )
            if non_block_definitions:
                fields_for_checksum["definitions"] = non_block_definitions
            else:
                # Pop off definitions entirely instead of empty dict for consistency
                # with the OpenAPI specification
                fields_for_checksum.pop("definitions")
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

        # The keys passed to `include` must NOT be aliases, else some items will be missed
        # i.e. must do `self.schema_` vs `self.schema` to get a `schema_ = Field(alias="schema")`
        # reported from https://github.com/PrefectHQ/prefect-dbt/issues/54
        data_keys = self.schema(by_alias=False)["properties"].keys()

        # `block_document_data`` must return the aliased version for it to show in the UI
        block_document_data = self.dict(by_alias=True, include=data_keys)

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
            version=cls.get_block_schema_version(),
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

        if code_example is None:
            # If no code example has been specified or extracted from the class
            # docstring, generate a sensible default
            code_example = cls._generate_code_example()

        return code_example

    @classmethod
    def _generate_code_example(cls) -> str:
        """Generates a default code example for the current class"""
        qualified_name = to_qualified_name(cls)
        module_str = ".".join(qualified_name.split(".")[:-1])
        class_name = cls.__name__
        block_variable_name = f'{cls.get_block_type_slug().replace("-", "_")}_block'

        return dedent(
            f"""\
        ```python
        from {module_str} import {class_name}

        {block_variable_name} = {class_name}.load("BLOCK_NAME")
        ```"""
        )

    @classmethod
    def _to_block_type(cls) -> BlockType:
        """
        Creates the corresponding block type of the block.

        Returns:
            BlockType: The corresponding block type.
        """
        return BlockType(
            id=cls._block_type_id or uuid4(),
            slug=cls.get_block_type_slug(),
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

        if (
            block_document.block_schema.checksum
            != block_cls._calculate_schema_checksum()
        ):
            warnings.warn(
                f"Block document has schema checksum {block_document.block_schema.checksum} "
                f"which does not match the schema checksum for class {block_cls.__name__!r}. "
                "This indicates the schema has changed and this block may not load.",
                stacklevel=2,
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
            name: The name or slug of the block document. A block document slug is a
                string with the format <block_type_slug>/<block_document_name>

        Raises:
            ValueError: If the requested block document is not found.

        Returns:
            An instance of the current class hydrated with the data stored in the
            block document with the specified name.

        Examples:
            Load from a Block subclass with a block document name:
            ```python
            class Custom(Block):
                message: str

            Custom(message="Hello!").save("my-custom-message")

            loaded_block = Custom.load("my-custom-message")
            ```

            Load from Block with a block document slug:
            class Custom(Block):
                message: str

            Custom(message="Hello!").save("my-custom-message")

            loaded_block = Block.load("custom/my-custom-message")
        """
        if cls.__name__ == "Block":
            block_type_slug, block_document_name = name.split("/", 1)
        else:
            block_type_slug = cls.get_block_type_slug()
            block_document_name = name
        async with prefect.client.get_client() as client:
            try:
                block_document = await client.read_block_document_by_name(
                    name=block_document_name, block_type_slug=block_type_slug
                )
            except prefect.exceptions.ObjectNotFound as e:
                raise ValueError(
                    f"Unable to find block document named {block_document_name} for block type {block_type_slug}"
                ) from e
        return cls._from_block_document(block_document)

    @staticmethod
    def is_block_class(block) -> bool:
        return inspect.isclass(block) and issubclass(block, Block)

    @classmethod
    @sync_compatible
    async def register_type_and_schema(cls, client: Optional["OrionClient"] = None):
        """
        Makes block available for configuration with current Orion server.
        Recursively registers all nested blocks. Registration is idempotent.

        Args:
            client: Optional Orion client to use for registering type and schema with
                Orion. A new client will be created and used if one is not provided.
        """
        if cls.__name__ == "Block":
            raise InvalidBlockRegistration(
                "`register_type_and_schema` should be called on a Block "
                "subclass and not on the Block class directly."
            )
        if ABC in getattr(cls, "__bases__", []):
            raise InvalidBlockRegistration(
                "`register_type_and_schema` should be called on a Block "
                "subclass and not on a Block interface class directly."
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
                block_type = await client.read_block_type_by_slug(
                    slug=cls.get_block_type_slug()
                )
                await client.update_block_type(
                    block_type_id=block_type.id, block_type=cls._to_block_type()
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
                                name=name, block_type_slug=self.get_block_type_slug()
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

    def _iter(self, *, include=None, exclude=None, **kwargs):
        # Injects the `block_type_slug` into serialized payloads for dispatch
        for key_value in super()._iter(include=include, exclude=exclude, **kwargs):
            yield key_value

        # Respect inclusion and exclusion still
        if include and "block_type_slug" not in include:
            return
        if exclude and "block_type_slug" in exclude:
            return

        yield "block_type_slug", self.get_block_type_slug()

    def __new__(cls: Type[Self], **kwargs) -> Self:
        """
        Create an instance of the Block subclass type if a `block_type_slug` is
        present in the data payload.
        """
        block_type_slug = kwargs.pop("block_type_slug", None)
        if block_type_slug:
            subcls = lookup_type(cls, dispatch_key=block_type_slug)
            m = super().__new__(subcls)
            # NOTE: This is a workaround for an obscure issue where copied models were
            #       missing attributes. This pattern is from Pydantic's
            #       `BaseModel._copy_and_set_values`.
            #       The issue this fixes could not be reproduced in unit tests that
            #       directly targeted dispatch handling and was only observed when
            #       copying then saving infrastructure blocks on deployment models.
            object.__setattr__(m, "__dict__", kwargs)
            object.__setattr__(m, "__fields_set__", set(kwargs.keys()))
            return m
        else:
            m = super().__new__(cls)
            object.__setattr__(m, "__dict__", kwargs)
            object.__setattr__(m, "__fields_set__", set(kwargs.keys()))
            return m
