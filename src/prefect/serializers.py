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

import base64
import io
from typing import Any, ClassVar, Generic, Optional, Union, overload

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
)
from typing_extensions import Self, TypeVar

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
    elif isinstance(obj, io.IOBase):
        return {
            "__class__": to_qualified_name(obj.__class__),
            "data": (
                f"<Prefect IOStream Placeholder: type={obj.__class__.__name__}, "
                f"repr={repr(obj)} (original content not read)>"
            ),
        }
    else:
        return {
            "__class__": to_qualified_name(obj.__class__),
            "data": custom_pydantic_encoder({}, obj),
        }


def prefect_json_object_decoder(result: dict[str, Any]) -> Any:
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
class Serializer(BaseModel, Generic[D]):
    """
    A serializer that can encode objects of type 'D' into bytes.
    """

    def __init__(self, **data: Any) -> None:
        type_string = (
            get_dispatch_key(self) if type(self) is not Serializer else "__base__"
        )
        data.setdefault("type", type_string)
        super().__init__(**data)

    @overload
    def __new__(cls, *, type: str, **kwargs: Any) -> "Serializer[Any]": ...

    @overload
    def __new__(cls, *, type: None = ..., **kwargs: Any) -> Self: ...

    def __new__(cls, **kwargs: Any) -> Union[Self, "Serializer[Any]"]:
        if type_ := kwargs.get("type"):
            try:
                subcls = lookup_type(cls, dispatch_key=type_)
            except KeyError as exc:
                raise ValidationError.from_exception_data(
                    title=cls.__name__,
                    line_errors=[{"type": str(exc), "input": kwargs["type"]}],
                    input_type="python",
                )

            return super().__new__(subcls)
        else:
            return super().__new__(cls)

    type: str

    def dumps(self, obj: D) -> bytes:
        """Encode the object into a blob of bytes."""
        raise NotImplementedError

    def loads(self, blob: bytes) -> D:
        """Decode the blob of bytes into an object."""
        raise NotImplementedError

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    @classmethod
    def __dispatch_key__(cls) -> Optional[str]:
        type_str = cls.model_fields["type"].default
        return type_str if isinstance(type_str, str) else None


class PickleSerializer(Serializer[D]):
    """
    Serializes objects using the pickle protocol.

    - Uses `cloudpickle` by default. See `picklelib` for using alternative libraries.
    - Stores the version of the pickle library to check for compatibility during
        deserialization.
    - Wraps pickles in base64 for safe transmission.
    """

    type: str = Field(default="pickle", frozen=True)

    picklelib: str = "cloudpickle"
    picklelib_version: Optional[str] = None

    @field_validator("picklelib")
    def check_picklelib(cls, value: str) -> str:
        return validate_picklelib(value)

    def dumps(self, obj: D) -> bytes:
        pickler = from_qualified_name(self.picklelib)
        blob = pickler.dumps(obj)
        return base64.encodebytes(blob)

    def loads(self, blob: bytes) -> D:
        pickler = from_qualified_name(self.picklelib)
        return pickler.loads(base64.decodebytes(blob))


class JSONSerializer(Serializer[D]):
    """
    Serializes data to JSON.

    Input types must be compatible with the stdlib json library.

    Wraps the `json` library to serialize to UTF-8 bytes instead of string types.
    """

    type: str = Field(default="json", frozen=True)

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
    dumps_kwargs: dict[str, Any] = Field(default_factory=dict)
    loads_kwargs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("dumps_kwargs")
    def dumps_kwargs_cannot_contain_default(
        cls, value: dict[str, Any]
    ) -> dict[str, Any]:
        return validate_dump_kwargs(value)

    @field_validator("loads_kwargs")
    def loads_kwargs_cannot_contain_object_hook(
        cls, value: dict[str, Any]
    ) -> dict[str, Any]:
        return validate_load_kwargs(value)

    def dumps(self, obj: D) -> bytes:
        json = from_qualified_name(self.jsonlib)
        kwargs = self.dumps_kwargs.copy()
        if self.object_encoder:
            kwargs["default"] = from_qualified_name(self.object_encoder)
        result = json.dumps(obj, **kwargs)
        if isinstance(result, str):
            # The standard library returns str but others may return bytes directly
            result = result.encode()
        return result

    def loads(self, blob: bytes) -> D:
        json = from_qualified_name(self.jsonlib)
        kwargs = self.loads_kwargs.copy()
        if self.object_decoder:
            kwargs["object_hook"] = from_qualified_name(self.object_decoder)
        return json.loads(blob.decode(), **kwargs)


class CompressedSerializer(Serializer[D]):
    """
    Wraps another serializer, compressing its output.
    Uses `lzma` by default. See `compressionlib` for using alternative libraries.

    Attributes:
        serializer: The serializer to use before compression.
        compressionlib: The import path of a compression module to use.
            Must have methods `compress(bytes) -> bytes` and `decompress(bytes) -> bytes`.
        level: If not null, the level of compression to pass to `compress`.
    """

    type: str = Field(default="compressed", frozen=True)

    serializer: Serializer[D]
    compressionlib: str = "lzma"

    @field_validator("serializer", mode="before")
    def validate_serializer(cls, value: Union[str, Serializer[D]]) -> Serializer[D]:
        return cast_type_names_to_serializers(value)

    @field_validator("compressionlib")
    def check_compressionlib(cls, value: str) -> str:
        return validate_compressionlib(value)

    def dumps(self, obj: D) -> bytes:
        blob = self.serializer.dumps(obj)
        compressor = from_qualified_name(self.compressionlib)
        return base64.encodebytes(compressor.compress(blob))

    def loads(self, blob: bytes) -> D:
        compressor = from_qualified_name(self.compressionlib)
        uncompressed = compressor.decompress(base64.decodebytes(blob))
        return self.serializer.loads(uncompressed)


class CompressedPickleSerializer(CompressedSerializer[D]):
    """
    A compressed serializer preconfigured to use the pickle serializer.
    """

    type: str = Field(default="compressed/pickle", frozen=True)

    serializer: Serializer[D] = Field(default_factory=PickleSerializer)


class CompressedJSONSerializer(CompressedSerializer[D]):
    """
    A compressed serializer preconfigured to use the json serializer.
    """

    type: str = Field(default="compressed/json", frozen=True)

    serializer: Serializer[D] = Field(default_factory=JSONSerializer)
