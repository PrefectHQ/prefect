"""
Serializer implementations for converting objects to bytes and bytes to objects.

All serializers are based on the `Serializer` class and include a `type` string that
allows them to be referenced without referencing the actual class. For example, you
can get often specify the `JSONSerializer` with the string "json". Some serializers
support additional settings for configuration of serialization. These are stored on
the instance so the same settings can be used to load saved objects.

All serializers must implement `dumps` and `loads` which convert objects to bytes and
bytes to an object respectively.
"""

import abc
import base64
from typing import Any, Dict, Generic, Optional, Type

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
)
from typing_extensions import Literal, Self, TypeVar

from prefect._internal.schemas.validators import (
    cast_type_names_to_serializers,
    validate_compressionlib,
    validate_dump_kwargs,
    validate_load_kwargs,
    validate_picklelib,
)
from prefect.utilities.dispatch import get_dispatch_key, lookup_type, register_base_type
from prefect.utilities.importtools import from_qualified_name, to_qualified_name
from prefect.utilities.pydantic import custom_pydantic_encoder

D = TypeVar("D", default=Any)


def prefect_json_object_encoder(obj: Any) -> Any:
    """
    `JSONEncoder.default` for encoding objects into JSON with extended type support.

    Raises a `TypeError` to fallback on other encoders on failure.
    """
    if isinstance(obj, BaseException):
        return {"__exc_type__": to_qualified_name(obj.__class__), "message": str(obj)}
    else:
        return {
            "__class__": to_qualified_name(obj.__class__),
            "data": custom_pydantic_encoder({}, obj),
        }


def prefect_json_object_decoder(result: dict):
    """
    `JSONDecoder.object_hook` for decoding objects from JSON when previously encoded
    with `prefect_json_object_encoder`
    """
    if "__class__" in result:
        return TypeAdapter(from_qualified_name(result["__class__"])).validate_python(
            result["data"]
        )
    elif "__exc_type__" in result:
        return from_qualified_name(result["__exc_type__"])(result["message"])
    else:
        return result


@register_base_type
class Serializer(BaseModel, Generic[D], abc.ABC):
    """
    A serializer that can encode objects of type 'D' into bytes.
    """

    def __init__(self, **data: Any) -> None:
        type_string = get_dispatch_key(self) if type(self) != Serializer else "__base__"
        data.setdefault("type", type_string)
        super().__init__(**data)

    def __new__(cls: Type[Self], **kwargs) -> Self:
        if "type" in kwargs:
            try:
                subcls = lookup_type(cls, dispatch_key=kwargs["type"])
            except KeyError as exc:
                raise ValidationError(errors=[exc], model=cls)

            return super().__new__(subcls)
        else:
            return super().__new__(cls)

    type: str

    @abc.abstractmethod
    def dumps(self, obj: D) -> bytes:
        """Encode the object into a blob of bytes."""

    @abc.abstractmethod
    def loads(self, blob: bytes) -> D:
        """Decode the blob of bytes into an object."""

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def __dispatch_key__(cls) -> str:
        type_str = cls.model_fields["type"].default
        return type_str if isinstance(type_str, str) else None


class PickleSerializer(Serializer):
    """
    Serializes objects using the pickle protocol.

    - Uses `cloudpickle` by default. See `picklelib` for using alternative libraries.
    - Stores the version of the pickle library to check for compatibility during
        deserialization.
    - Wraps pickles in base64 for safe transmission.
    """

    type: Literal["pickle"] = "pickle"

    picklelib: str = "cloudpickle"
    picklelib_version: Optional[str] = None

    @field_validator("picklelib")
    def check_picklelib(cls, value):
        return validate_picklelib(value)

    # @model_validator(mode="before")
    # def check_picklelib_version(cls, values):
    #     return validate_picklelib_version(values)

    def dumps(self, obj: Any) -> bytes:
        pickler = from_qualified_name(self.picklelib)
        blob = pickler.dumps(obj)
        return base64.encodebytes(blob)

    def loads(self, blob: bytes) -> Any:
        pickler = from_qualified_name(self.picklelib)
        return pickler.loads(base64.decodebytes(blob))


class JSONSerializer(Serializer):
    """
    Serializes data to JSON.

    Input types must be compatible with the stdlib json library.

    Wraps the `json` library to serialize to UTF-8 bytes instead of string types.
    """

    type: Literal["json"] = "json"

    jsonlib: str = "json"
    object_encoder: Optional[str] = Field(
        default="prefect.serializers.prefect_json_object_encoder",
        description=(
            "An optional callable to use when serializing objects that are not "
            "supported by the JSON encoder. By default, this is set to a callable that "
            "adds support for all types supported by "
        ),
    )
    object_decoder: Optional[str] = Field(
        default="prefect.serializers.prefect_json_object_decoder",
        description=(
            "An optional callable to use when deserializing objects. This callable "
            "is passed each dictionary encountered during JSON deserialization. "
            "By default, this is set to a callable that deserializes content created "
            "by our default `object_encoder`."
        ),
    )
    dumps_kwargs: Dict[str, Any] = Field(default_factory=dict)
    loads_kwargs: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("dumps_kwargs")
    def dumps_kwargs_cannot_contain_default(cls, value):
        return validate_dump_kwargs(value)

    @field_validator("loads_kwargs")
    def loads_kwargs_cannot_contain_object_hook(cls, value):
        return validate_load_kwargs(value)

    def dumps(self, data: Any) -> bytes:
        json = from_qualified_name(self.jsonlib)
        kwargs = self.dumps_kwargs.copy()
        if self.object_encoder:
            kwargs["default"] = from_qualified_name(self.object_encoder)
        result = json.dumps(data, **kwargs)
        if isinstance(result, str):
            # The standard library returns str but others may return bytes directly
            result = result.encode()
        return result

    def loads(self, blob: bytes) -> Any:
        json = from_qualified_name(self.jsonlib)
        kwargs = self.loads_kwargs.copy()
        if self.object_decoder:
            kwargs["object_hook"] = from_qualified_name(self.object_decoder)
        return json.loads(blob.decode(), **kwargs)


class CompressedSerializer(Serializer):
    """
    Wraps another serializer, compressing its output.
    Uses `lzma` by default. See `compressionlib` for using alternative libraries.

    Attributes:
        serializer: The serializer to use before compression.
        compressionlib: The import path of a compression module to use.
            Must have methods `compress(bytes) -> bytes` and `decompress(bytes) -> bytes`.
        level: If not null, the level of compression to pass to `compress`.
    """

    type: Literal["compressed"] = "compressed"

    serializer: Serializer
    compressionlib: str = "lzma"

    @field_validator("serializer", mode="before")
    def validate_serializer(cls, value):
        return cast_type_names_to_serializers(value)

    @field_validator("compressionlib")
    def check_compressionlib(cls, value):
        return validate_compressionlib(value)

    def dumps(self, obj: Any) -> bytes:
        blob = self.serializer.dumps(obj)
        compressor = from_qualified_name(self.compressionlib)
        return base64.encodebytes(compressor.compress(blob))

    def loads(self, blob: bytes) -> Any:
        compressor = from_qualified_name(self.compressionlib)
        uncompressed = compressor.decompress(base64.decodebytes(blob))
        return self.serializer.loads(uncompressed)


class CompressedPickleSerializer(CompressedSerializer):
    """
    A compressed serializer preconfigured to use the pickle serializer.
    """

    type: Literal["compressed/pickle"] = "compressed/pickle"

    serializer: Serializer = Field(default_factory=PickleSerializer)


class CompressedJSONSerializer(CompressedSerializer):
    """
    A compressed serializer preconfigured to use the json serializer.
    """

    type: Literal["compressed/json"] = "compressed/json"

    serializer: Serializer = Field(default_factory=JSONSerializer)
