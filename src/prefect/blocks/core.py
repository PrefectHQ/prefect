import hashlib
import html
import inspect
import sys
import warnings
from abc import ABC
from functools import partial
from textwrap import dedent
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    FrozenSet,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_origin,
)
from uuid import UUID, uuid4

from griffe.dataclasses import Docstring
from griffe.docstrings.dataclasses import DocstringSection, DocstringSectionKind
from griffe.docstrings.parsers import Parser, parse
from packaging.version import InvalidVersion, Version
from pydantic import (
    BaseModel,
    ConfigDict,
    HttpUrl,
    PrivateAttr,
    SecretBytes,
    SecretStr,
    SerializationInfo,
    ValidationError,
    model_serializer,
)
from pydantic.json_schema import GenerateJsonSchema
from typing_extensions import Literal, ParamSpec, Self, get_args

import prefect
import prefect.exceptions
from prefect.client.schemas import (
    DEFAULT_BLOCK_SCHEMA_VERSION,
    BlockDocument,
    BlockSchema,
    BlockType,
    BlockTypeUpdate,
)
from prefect.client.utilities import inject_client
from prefect.events import emit_event
from prefect.logging.loggers import disable_logger
from prefect.types import SecretDict
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.collections import listrepr, remove_nested_keys, visit_collection
from prefect.utilities.dispatch import lookup_type, register_base_type
from prefect.utilities.hashing import hash_objects
from prefect.utilities.importtools import to_qualified_name
from prefect.utilities.pydantic import handle_secret_render
from prefect.utilities.slugify import slugify

if TYPE_CHECKING:
    from pydantic.main import IncEx

    from prefect.client.orchestration import PrefectClient

R = TypeVar("R")
P = ParamSpec("P")

ResourceTuple = Tuple[Dict[str, Any], List[Dict[str, Any]]]


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


def _is_subclass(cls, parent_cls) -> bool:
    """
    Checks if a given class is a subclass of another class. Unlike issubclass,
    this will not throw an exception if cls is an instance instead of a type.
    """
    return inspect.isclass(cls) and issubclass(cls, parent_cls)


def _collect_secret_fields(
    name: str, type_: Type[BaseModel], secrets: List[str]
) -> None:
    """
    Recursively collects all secret fields from a given type and adds them to the
    secrets list, supporting nested Union / BaseModel fields. Also, note, this function
    mutates the input secrets list, thus does not return anything.
    """
    if get_origin(type_) is Union:
        for union_type in get_args(type_):
            _collect_secret_fields(name, union_type, secrets)
        return
    elif _is_subclass(type_, BaseModel):
        for field_name, field in type_.model_fields.items():
            _collect_secret_fields(f"{name}.{field_name}", field.annotation, secrets)
        return

    if type_ in (SecretStr, SecretBytes):
        secrets.append(name)
    elif type_ == SecretDict:
        # Append .* to field name to signify that all values under this
        # field are secret and should be obfuscated.
        secrets.append(f"{name}.*")
    elif Block.is_block_class(type_):
        secrets.extend(
            f"{name}.{s}" for s in type_.model_json_schema()["secret_fields"]
        )


def _should_update_block_type(
    local_block_type: BlockType, server_block_type: BlockType
) -> bool:
    """
    Compares the fields of `local_block_type` and `server_block_type`.
    Only compare the possible updatable fields as defined by `BlockTypeUpdate.updatable_fields`
    Returns True if they are different, otherwise False.
    """
    fields = BlockTypeUpdate.updatable_fields()

    local_block_fields = local_block_type.model_dump(include=fields, exclude_unset=True)
    server_block_fields = server_block_type.model_dump(
        include=fields, exclude_unset=True
    )

    if local_block_fields.get("description") is not None:
        local_block_fields["description"] = html.unescape(
            local_block_fields["description"]
        )
    if local_block_fields.get("code_example") is not None:
        local_block_fields["code_example"] = html.unescape(
            local_block_fields["code_example"]
        )

    if server_block_fields.get("description") is not None:
        server_block_fields["description"] = html.unescape(
            server_block_fields["description"]
        )
    if server_block_fields.get("code_example") is not None:
        server_block_fields["code_example"] = html.unescape(
            server_block_fields["code_example"]
        )

    return server_block_fields != local_block_fields


class BlockNotSavedError(RuntimeError):
    """
    Raised when a given block is not saved and an operation that requires
    the block to be saved is attempted.
    """

    pass


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
    # A wildcard (*) means that all fields under a given key are secret.
    # for example: ["x", "y", "z.*", "child.a"]
    # means the top-level keys "x" and "y", all keys under "z", and the key "a" of a block
    # nested under the "child" key are all secret. There is no limit to nesting.
    secrets = schema["secret_fields"] = []
    for name, field in model.model_fields.items():
        _collect_secret_fields(name, field.annotation, secrets)

    # create block schema references
    refs = schema["block_schema_references"] = {}
    for name, field in model.model_fields.items():
        if Block.is_block_class(field.annotation):
            refs[name] = field.annotation._to_block_schema_reference_dict()
        if get_origin(field.annotation) in [Union, list]:
            for type_ in get_args(field.annotation):
                if Block.is_block_class(type_):
                    if isinstance(refs.get(name), list):
                        refs[name].append(type_._to_block_schema_reference_dict())
                    elif isinstance(refs.get(name), dict):
                        refs[name] = [
                            refs[name],
                            type_._to_block_schema_reference_dict(),
                        ]
                    else:
                        refs[name] = type_._to_block_schema_reference_dict()


@register_base_type
class Block(BaseModel, ABC):
    """
    A base class for implementing a block that wraps an external service.

    This class can be defined with an arbitrary set of fields and methods, and
    couples business logic with data contained in an block document.
    `_block_document_name`, `_block_document_id`, `_block_schema_id`, and
    `_block_type_id` are reserved by Prefect as Block metadata fields, but
    otherwise a Block can implement arbitrary logic. Blocks can be instantiated
    without populating these metadata fields, but can only be used interactively,
    not with the Prefect API.

    Instead of the __init__ method, a block implementation allows the
    definition of a `block_initialization` method that is called after
    initialization.
    """

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra=schema_extra,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.block_initialization()

    def __str__(self) -> str:
        return self.__repr__()

    def __repr_args__(self):
        repr_args = super().__repr_args__()
        data_keys = self.model_json_schema()["properties"].keys()
        return [
            (key, value) for key, value in repr_args if key is None or key in data_keys
        ]

    def block_initialization(self) -> None:
        pass

    # -- private class variables
    # set by the class itself

    # Attribute to customize the name of the block type created
    # when the block is registered with the API. If not set, block
    # type name will default to the class name.
    _block_type_name: ClassVar[Optional[str]] = None
    _block_type_slug: ClassVar[Optional[str]] = None

    # Attributes used to set properties on a block type when registered
    # with the API.
    _logo_url: ClassVar[Optional[HttpUrl]] = None
    _documentation_url: ClassVar[Optional[HttpUrl]] = None
    _description: ClassVar[Optional[str]] = None
    _code_example: ClassVar[Optional[str]] = None
    _block_type_id: ClassVar[Optional[UUID]] = None
    _block_schema_id: ClassVar[Optional[UUID]] = None
    _block_schema_capabilities: ClassVar[Optional[List[str]]] = None
    _block_schema_version: ClassVar[Optional[str]] = None

    # -- private instance variables
    # these are set when blocks are loaded from the API

    _block_document_id: Optional[UUID] = PrivateAttr(None)
    _block_document_name: Optional[str] = PrivateAttr(None)
    _is_anonymous: Optional[bool] = PrivateAttr(None)

    # Exclude `save` as it uses the `sync_compatible` decorator and needs to be
    # decorated directly.
    _events_excluded_methods = ["block_initialization", "save", "dict"]

    @classmethod
    def __dispatch_key__(cls):
        if cls.__name__ == "Block":
            return None  # The base class is abstract
        return block_schema_to_key(cls._to_block_schema())

    @model_serializer(mode="wrap")
    def ser_model(self, handler: Callable, info: SerializationInfo) -> Any:
        jsonable_self = handler(self)
        if (ctx := info.context) and ctx.get("include_secrets") is True:
            jsonable_self.update(
                {
                    field_name: visit_collection(
                        expr=getattr(self, field_name),
                        visit_fn=partial(handle_secret_render, context=ctx),
                        return_data=True,
                    )
                    for field_name in self.model_fields
                }
            )
        if extra_fields := {
            "block_type_slug": self.get_block_type_slug(),
            "_block_document_id": self._block_document_id,
            "_block_document_name": self._block_document_name,
            "_is_anonymous": self._is_anonymous,
        }:
            jsonable_self |= {
                key: value for key, value in extra_fields.items() if value is not None
            }
        return jsonable_self

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
                version = Version(top_level_module.__version__)
                # Strips off any local version information
                return version.base_version
            except (AttributeError, InvalidVersion):
                # Module does not have a __version__ attribute or is not a parsable format
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
            cls.model_json_schema()
            if block_schema_fields is None
            else block_schema_fields
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
        include_secrets: bool = False,
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
        data_keys = self.model_json_schema(by_alias=False)["properties"].keys()

        # `block_document_data`` must return the aliased version for it to show in the UI
        block_document_data = self.model_dump(
            by_alias=True,
            include=data_keys,
            context={"include_secrets": include_secrets},
        )

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
        fields = cls.model_json_schema()
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
        with disable_logger("griffe.docstrings.google"):
            with disable_logger("griffe.agents.nodes"):
                docstring = Docstring(cls.__doc__)
                parsed = parse(docstring, Parser.google)
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
            dedent(text=cls._code_example) if cls._code_example is not None else None
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
    def _from_block_document(cls, block_document: BlockDocument) -> Self:
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

        block = block_cls.model_validate(block_document.data)
        block._block_document_id = block_document.id
        block.__class__._block_schema_id = block_document.block_schema_id
        block.__class__._block_type_id = block_document.block_type_id
        block._block_document_name = block_document.name
        block._is_anonymous = block_document.is_anonymous
        block._define_metadata_on_nested_blocks(
            block_document.block_document_references
        )

        resources: Optional[ResourceTuple] = block._event_method_called_resources()
        if resources:
            kind = block._event_kind()
            resource, related = resources
            emit_event(event=f"{kind}.loaded", resource=resource, related=related)

        return block

    def _event_kind(self) -> str:
        return f"prefect.block.{self.get_block_type_slug()}"

    def _event_method_called_resources(self) -> Optional[ResourceTuple]:
        if not (self._block_document_id and self._block_document_name):
            return None

        return (
            {
                "prefect.resource.id": (
                    f"prefect.block-document.{self._block_document_id}"
                ),
                "prefect.resource.name": self._block_document_name,
            },
            [
                {
                    "prefect.resource.id": (
                        f"prefect.block-type.{self.get_block_type_slug()}"
                    ),
                    "prefect.resource.role": "block-type",
                }
            ],
        )

    @classmethod
    def get_block_class_from_schema(cls: Type[Self], schema: BlockSchema) -> Type[Self]:
        """
        Retrieve the block class implementation given a schema.
        """
        return cls.get_block_class_from_key(block_schema_to_key(schema))

    @classmethod
    def get_block_class_from_key(cls: Type[Self], key: str) -> Type[Self]:
        """
        Retrieve the block class implementation given a key.
        """
        # Ensure collections are imported and have the opportunity to register types
        # before looking up the block class
        prefect.plugins.load_prefect_collections()

        return lookup_type(cls, key)

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
    @inject_client
    async def _get_block_document(
        cls,
        name: str,
        client: Optional["PrefectClient"] = None,
    ):
        if cls.__name__ == "Block":
            block_type_slug, block_document_name = name.split("/", 1)
        else:
            block_type_slug = cls.get_block_type_slug()
            block_document_name = name

        try:
            block_document = await client.read_block_document_by_name(
                name=block_document_name, block_type_slug=block_type_slug
            )
        except prefect.exceptions.ObjectNotFound as e:
            raise ValueError(
                f"Unable to find block document named {block_document_name} for block"
                f" type {block_type_slug}"
            ) from e

        return block_document, block_document_name

    @classmethod
    @sync_compatible
    @inject_client
    async def load(
        cls,
        name: str,
        validate: bool = True,
        client: Optional["PrefectClient"] = None,
    ) -> "Self":
        """
        Retrieves data from the block document with the given name for the block type
        that corresponds with the current class and returns an instantiated version of
        the current class with the data stored in the block document.

        If a block document for a given block type is saved with a different schema
        than the current class calling `load`, a warning will be raised.

        If the current class schema is a subset of the block document schema, the block
        can be loaded as normal using the default `validate = True`.

        If the current class schema is a superset of the block document schema, `load`
        must be called with `validate` set to False to prevent a validation error. In
        this case, the block attributes will default to `None` and must be set manually
        and saved to a new block document before the block can be used as expected.

        Args:
            name: The name or slug of the block document. A block document slug is a
                string with the format <block_type_slug>/<block_document_name>
            validate: If False, the block document will be loaded without Pydantic
                validating the block schema. This is useful if the block schema has
                changed client-side since the block document referred to by `name` was saved.
            client: The client to use to load the block document. If not provided, the
                default client will be injected.

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
            ```python
            class Custom(Block):
                message: str

            Custom(message="Hello!").save("my-custom-message")

            loaded_block = Block.load("custom/my-custom-message")
            ```

            Migrate a block document to a new schema:
            ```python
            # original class
            class Custom(Block):
                message: str

            Custom(message="Hello!").save("my-custom-message")

            # Updated class with new required field
            class Custom(Block):
                message: str
                number_of_ducks: int

            loaded_block = Custom.load("my-custom-message", validate=False)

            # Prints UserWarning about schema mismatch

            loaded_block.number_of_ducks = 42

            loaded_block.save("my-custom-message", overwrite=True)
            ```
        """
        block_document, block_document_name = await cls._get_block_document(name)

        try:
            return cls._from_block_document(block_document)
        except ValidationError as e:
            if not validate:
                missing_fields = tuple(err["loc"][0] for err in e.errors())
                missing_block_data = {field: None for field in missing_fields}
                warnings.warn(
                    f"Could not fully load {block_document_name!r} of block type"
                    f" {cls.get_block_type_slug()!r} - this is likely because one or more"
                    " required fields were added to the schema for"
                    f" {cls.__name__!r} that did not exist on the class when this block"
                    " was last saved. Please specify values for new field(s):"
                    f" {listrepr(missing_fields)}, then run"
                    f' `{cls.__name__}.save("{block_document_name}", overwrite=True)`,'
                    " and load this block again before attempting to use it."
                )
                return cls.model_construct(**block_document.data, **missing_block_data)
            raise RuntimeError(
                f"Unable to load {block_document_name!r} of block type"
                f" {cls.get_block_type_slug()!r} due to failed validation. To load without"
                " validation, try loading again with `validate=False`."
            ) from e

    @staticmethod
    def is_block_class(block) -> bool:
        return _is_subclass(block, Block)

    @staticmethod
    def annotation_refers_to_block_class(annotation: Any) -> bool:
        if Block.is_block_class(annotation):
            return True

        if get_origin(annotation) is Union:
            for annotation in get_args(annotation):
                if Block.is_block_class(annotation):
                    return True

        return False

    @classmethod
    @sync_compatible
    @inject_client
    async def register_type_and_schema(cls, client: "PrefectClient" = None):
        """
        Makes block available for configuration with current Prefect API.
        Recursively registers all nested blocks. Registration is idempotent.

        Args:
            client: Optional client to use for registering type and schema with the
                Prefect API. A new client will be created and used if one is not
                provided.
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

        for field in cls.model_fields.values():
            if Block.is_block_class(field.annotation):
                await field.annotation.register_type_and_schema(client=client)
            if get_origin(field.annotation) is Union:
                for annotation in get_args(field.annotation):
                    if Block.is_block_class(annotation):
                        await annotation.register_type_and_schema(client=client)

        try:
            block_type = await client.read_block_type_by_slug(
                slug=cls.get_block_type_slug()
            )

            cls._block_type_id = block_type.id

            local_block_type = cls._to_block_type()
            if _should_update_block_type(
                local_block_type=local_block_type, server_block_type=block_type
            ):
                await client.update_block_type(
                    block_type_id=block_type.id, block_type=local_block_type
                )
        except prefect.exceptions.ObjectNotFound:
            block_type = await client.create_block_type(block_type=cls._to_block_type())
            cls._block_type_id = block_type.id

        try:
            block_schema = await client.read_block_schema_by_checksum(
                checksum=cls._calculate_schema_checksum(),
                version=cls.get_block_schema_version(),
            )
        except prefect.exceptions.ObjectNotFound:
            block_schema = await client.create_block_schema(
                block_schema=cls._to_block_schema(block_type_id=block_type.id)
            )

        cls._block_schema_id = block_schema.id

    @inject_client
    async def _save(
        self,
        name: Optional[str] = None,
        is_anonymous: bool = False,
        overwrite: bool = False,
        client: Optional["PrefectClient"] = None,
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
            if self._block_document_name is None:
                raise ValueError(
                    "You're attempting to save a block document without a name."
                    " Please either call `save` with a `name` or pass"
                    " `is_anonymous=True` to save an anonymous block."
                )
            else:
                name = self._block_document_name

        self._is_anonymous = is_anonymous

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
                    existing_block_document = await client.read_block_document_by_name(
                        name=name, block_type_slug=self.get_block_type_slug()
                    )
                    block_document_id = existing_block_document.id
                await client.update_block_document(
                    block_document_id=block_document_id,
                    block_document=self._to_block_document(
                        name=name, include_secrets=True
                    ),
                )
                block_document = await client.read_block_document(
                    block_document_id=block_document_id
                )
            else:
                raise ValueError(
                    "You are attempting to save values with a name that is already in"
                    " use for this block type. If you would like to overwrite the"
                    " values that are saved, then save with `overwrite=True`."
                ) from err

        # Update metadata on block instance for later use.
        self._block_document_name = block_document.name
        self._block_document_id = block_document.id
        return self._block_document_id

    @sync_compatible
    async def save(
        self,
        name: Optional[str] = None,
        overwrite: bool = False,
        client: Optional["PrefectClient"] = None,
    ):
        """
        Saves the values of a block as a block document.

        Args:
            name: User specified name to give saved block document which can later be used to load the
                block document.
            overwrite: Boolean value specifying if values should be overwritten if a block document with
                the specified name already exists.

        """
        document_id = await self._save(name=name, overwrite=overwrite, client=client)

        return document_id

    @classmethod
    @sync_compatible
    @inject_client
    async def delete(
        cls,
        name: str,
        client: Optional["PrefectClient"] = None,
    ):
        block_document, block_document_name = await cls._get_block_document(name)

        await client.delete_block_document(block_document.id)

    def __new__(cls: Type[Self], **kwargs) -> Self:
        """
        Create an instance of the Block subclass type if a `block_type_slug` is
        present in the data payload.
        """
        block_type_slug = kwargs.pop("block_type_slug", None)
        if block_type_slug:
            subcls = lookup_type(cls, dispatch_key=block_type_slug)
            return super().__new__(subcls)
        else:
            return super().__new__(cls)

    def get_block_placeholder(self) -> str:
        """
        Returns the block placeholder for the current block which can be used for
        templating.

        Returns:
            str: The block placeholder for the current block in the format
                `prefect.blocks.{block_type_name}.{block_document_name}`

        Raises:
            BlockNotSavedError: Raised if the block has not been saved.

        If a block has not been saved, the return value will be `None`.
        """
        block_document_name = self._block_document_name
        if not block_document_name:
            raise BlockNotSavedError(
                "Could not generate block placeholder for unsaved block."
            )

        return f"prefect.blocks.{self.get_block_type_slug()}.{block_document_name}"

    @classmethod
    def model_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = "#/definitions/{model}",
        schema_generator: Type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: Literal["validation", "serialization"] = "validation",
    ) -> Dict[str, Any]:
        """TODO: stop overriding this method - use GenerateSchema in ConfigDict instead?"""
        schema = super().model_json_schema(
            by_alias, ref_template, schema_generator, mode
        )

        # ensure backwards compatibility by copying $defs into definitions
        if "$defs" in schema:
            schema["definitions"] = schema.pop("$defs")

        # we aren't expecting these additional fields in the schema
        if "additionalProperties" in schema:
            schema.pop("additionalProperties")

        for _, definition in schema.get("definitions", {}).items():
            if "additionalProperties" in definition:
                definition.pop("additionalProperties")

        return schema

    @classmethod
    def model_validate(
        cls: type[Self],
        obj: Any,
        *,
        strict: Optional[bool] = None,
        from_attributes: Optional[bool] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Self:
        if isinstance(obj, dict):
            extra_serializer_fields = {
                "_block_document_id",
                "_block_document_name",
                "_is_anonymous",
            }.intersection(obj.keys())
            for field in extra_serializer_fields:
                obj.pop(field, None)

        return super().model_validate(
            obj, strict=strict, from_attributes=from_attributes, context=context
        )

    def model_dump(
        self,
        *,
        mode: Union[Literal["json", "python"], str] = "python",
        include: "IncEx" = None,
        exclude: "IncEx" = None,
        context: Optional[Dict[str, Any]] = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: Union[bool, Literal["none", "warn", "error"]] = True,
        serialize_as_any: bool = False,
    ) -> Dict[str, Any]:
        d = super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
            serialize_as_any=serialize_as_any,
        )

        extra_serializer_fields = {
            "block_type_slug",
            "_block_document_id",
            "_block_document_name",
            "_is_anonymous",
        }.intersection(d.keys())

        for field in extra_serializer_fields:
            if (include and field not in include) or (exclude and field in exclude):
                d.pop(field)

        return d
