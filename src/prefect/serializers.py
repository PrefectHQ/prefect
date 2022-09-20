"""
Data serializer implementations

These serializers are registered for use with `DataDocument` types
"""
import base64
import json
from typing import TYPE_CHECKING, Any, Callable, List, Optional

import cloudpickle

from prefect.orion.serializers import register_serializer

if TYPE_CHECKING:
    from prefect.packaging.base import PackageManifest
    from prefect.results import _Result

import abc
import base64
import json
import warnings
from typing import Any, Generic, TypeVar

import cloudpickle
import pydantic
from anyio._core._exceptions import ExceptionGroup
from pydantic import BaseModel
from pydantic.json import pydantic_encoder
from typing_extensions import Literal

from prefect.orion.serializers import register_serializer
from prefect.utilities.importtools import from_qualified_name, to_qualified_name
from prefect.utilities.pydantic import add_type_dispatch

D = TypeVar("D")


def _exception_group_reduce_patch(self: ExceptionGroup):
    return (self.__class__, (self.exceptions,))


class PrefectJSONEncoder(json.encoder.JSONEncoder):
    def default(self, obj):
        try:
            return {
                "__class__": to_qualified_name(obj.__class__),
                "data": pydantic_encoder(obj),
            }
        except TypeError:
            # Allow the superlcass to raise the `TypeError`
            pass
        return super().default(obj)


class PrefectJSONDecoder(json.decoder.JSONDecoder):
    def __init__(
        self, *, object_hook: Optional[Callable[[dict], Any]] = None, **kwargs
    ):
        # Allow users to specify an object hook still by chaining the hook with our
        # default
        object_hook = self.chain_hooks(object_hook, self.class_object_hook)
        super().__init__(object_hook=object_hook, **kwargs)

    @staticmethod
    def chain_hooks(*hooks: Optional[Callable[[dict], Any]]):
        """
        Chain multiple object hooks, calling each in order until a hook changes the
        result to a non-dictionary type.
        """

        def object_hook(result: dict):
            for hook in hooks:
                if hook is not None:
                    result = hook(result)
                if not isinstance(result, dict):
                    # The hook handled this type
                    break
            return result

        return object_hook

    @staticmethod
    def class_object_hook(result: dict):
        """
        Object hook for restoring objects encoded with the Pydantic encoder at
        `pydantic.json.pydantic_encoder`
        """
        if "__class__" in result:
            return pydantic.parse_obj_as(
                from_qualified_name(result["__class__"]), result["data"]
            )
        return result


@add_type_dispatch
class Serializer(BaseModel, Generic[D], abc.ABC):
    """
    A serializer that can encode objects of type 'D' into bytes.
    """

    type: str

    def dumps(self, obj: D) -> bytes:
        """Encode the object into a blob of bytes."""

    def loads(self, blob: bytes) -> D:
        """Decode the blob of bytes into an object."""

    class Config:
        extra = "forbid"


class PickleSerializer(Serializer):
    """
    Serializes objects using the pickle protocol.

    If using cloudpickle, you may specify a list of 'pickle_modules'. These modules will
    be serialized by value instead of by reference, which means they do not have to be
    installed in the runtime location. This is especially useful for serializing objects
    that rely on local packages.

    Wraps pickles in base64 for safe transmission.
    """

    type: Literal["pickle"] = "pickle"

    picklelib: str = "cloudpickle"
    picklelib_version: str = None
    pickle_modules: List[str] = pydantic.Field(default_factory=list)

    @pydantic.validator("picklelib")
    def check_picklelib(cls, value):
        """
        Check that the given pickle library is importable and has dumps/loads methods.
        """
        try:
            pickler = from_qualified_name(value)
        except (ImportError, AttributeError) as exc:
            raise ValueError(
                f"Failed to import requested pickle library: {value!r}."
            ) from exc

        if not callable(getattr(pickler, "dumps", None)):
            raise ValueError(
                f"Pickle library at {value!r} does not have a 'dumps' method."
            )

        if not callable(getattr(pickler, "loads", None)):
            raise ValueError(
                f"Pickle library at {value!r} does not have a 'loads' method."
            )

        return value

    @pydantic.root_validator
    def check_picklelib_version(cls, values):
        """
        Infers a default value for `picklelib_version` if null or ensures it matches
        the version retrieved from the `pickelib`.
        """
        picklelib = values.get("picklelib")
        picklelib_version = values.get("picklelib_version")

        if not picklelib:
            raise ValueError("Unable to check version of unrecognized picklelib module")

        pickler = from_qualified_name(picklelib)
        pickler_version = getattr(pickler, "__version__", None)

        if not picklelib_version:
            values["picklelib_version"] = pickler_version
        elif picklelib_version != pickler_version:
            warnings.warn(
                f"Mismatched {picklelib!r} versions. Found {pickler_version} in the "
                f"environment but {picklelib_version} was requested. This may cause "
                "the serializer to fail.",
                RuntimeWarning,
                stacklevel=3,
            )

        return values

    @pydantic.root_validator
    def check_picklelib_and_modules(cls, values):
        """
        Prevents modules from being specified if picklelib is not cloudpickle
        """
        if values.get("picklelib") != "cloudpickle" and values.get("pickle_modules"):
            raise ValueError(
                f"`pickle_modules` cannot be used without 'cloudpickle'. Got {values.get('picklelib')!r}."
            )
        return values

    def dumps(self, obj: Any) -> bytes:
        pickler = from_qualified_name(self.picklelib)

        for module in self.pickle_modules:
            pickler.register_pickle_by_value(from_qualified_name(module))

        blob = pickler.dumps(obj)

        for module in self.pickle_modules:
            # Restore the pickler settings
            pickler.unregister_pickle_by_value(from_qualified_name(module))

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
    encoder_cls: str = "prefect.serializers.PrefectJSONEncoder"
    decoder_cls: str = "prefect.serializers.PrefectJSONDecoder"

    def dumps(self, data: Any) -> bytes:
        json = from_qualified_name(self.jsonlib)
        kwargs = {}
        if self.encoder_cls:
            kwargs["cls"] = from_qualified_name(self.encoder_cls)
        return json.dumps(data, **kwargs).encode()

    def loads(self, blob: bytes) -> Any:
        json = from_qualified_name(self.jsonlib)
        kwargs = {}
        if self.decoder_cls:
            kwargs["cls"] = from_qualified_name(self.decoder_cls)
        return json.loads(blob.decode(), **kwargs)


# DEPRECATED
# Data document serializers ----------------


@register_serializer("json")
class DocumentJSONSerializer:
    """
    Serializes data to JSON.

    Input types must be compatible with the stdlib json library.

    Wraps the `json` library to serialize to UTF-8 bytes instead of string types.
    """

    @staticmethod
    def dumps(data: Any) -> bytes:
        return json.dumps(data).encode()

    @staticmethod
    def loads(blob: bytes) -> Any:
        return json.loads(blob.decode())


@register_serializer("text")
class TextSerializer:
    @staticmethod
    def dumps(data: str) -> bytes:
        return data.encode()

    @staticmethod
    def loads(blob: bytes) -> str:
        return blob.decode()


@register_serializer("cloudpickle")
class DocumentPickleSerializer:
    """
    Serializes arbitrary objects using the pickle protocol.

    Wraps `cloudpickle` to encode bytes in base64 for safe transmission.
    """

    @staticmethod
    def dumps(data: Any) -> bytes:
        data_bytes = cloudpickle.dumps(data)

        return base64.encodebytes(data_bytes)

    @staticmethod
    def loads(blob: bytes) -> Any:
        return cloudpickle.loads(base64.decodebytes(blob))
        # TODO: Consider adding python version data to pickle payloads to raise
        #       more helpful errors for users.
        #       A TypeError("expected bytes-like object, not int") will be raised if
        #       a document is deserialized by Python 3.7 and serialized by 3.8+


@register_serializer("package-manifest")
class PackageManifestSerializer:
    """
    Serializes a package manifest.
    """

    @staticmethod
    def dumps(data: "PackageManifest") -> bytes:
        return data.json().encode()

    @staticmethod
    def loads(blob: bytes) -> "PackageManifest":
        from prefect.packaging.base import PackageManifest

        return PackageManifest.parse_raw(blob)


@register_serializer("result")
class ResultSerializer:
    """
    Serializes a result object
    """

    @staticmethod
    def dumps(data: "_Result") -> bytes:
        return data.json().encode()

    @staticmethod
    def loads(blob: bytes) -> "_Result":
        from prefect.results import _Result

        return _Result.parse_raw(blob)
