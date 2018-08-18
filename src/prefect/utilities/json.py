# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

"""
Facilities for serializing/deserializing Python objects to JSON.
"""
import base64
import binascii
import datetime
import inspect
import json
import sys
import types
import uuid
import warnings
from functools import singledispatch, partial
from typing import Any, Callable, Dict, Generic, Optional, Type, TypeVar, Union

import dateutil.parser
from cryptography.fernet import Fernet

import prefect

JSON_CODECS_KEYS = dict()  # type: Dict[str, 'JSONCodec']
CODEC_PREFIX = "//"

O = TypeVar("O")
J = TypeVar("J", str, dict, list, tuple, int, float)

__all__ = [
    "to_qualified_name",
    "register_json_codec",
    "JSONCodec",
    "Serializable",
    "dumps",
    "loads",
]


def from_qualified_name(obj_str: str) -> object:
    """
    Retrives an object from a fully qualified string path. The object must be
    imported in advance.
    """

    path_components = obj_str.split(".")
    for i in range(len(path_components), 0, -1):
        module_path = ".".join(path_components[:i])
        # import ipdb; ipdb.set_trace()
        if module_path in sys.modules:
            obj = sys.modules[module_path]
            for p in path_components[i:]:
                obj = getattr(obj, p)
            return obj
    raise ValueError(
        "Couldn't load \"{}\"; maybe it hasn't been imported yet?".format(obj_str)
    )


def to_qualified_name(obj: Any) -> str:
    return obj.__module__ + "." + obj.__qualname__


def register_json_codec(register_type: Type = None) -> "JSONCodec":
    """
    Decorator that registers a JSON Codec to a corresponding codec_key.

    If a register_type is provided, the codec will automatically be applied
    to that type.

    Whenever the codec is used to serialize an object, the result will be a
    key-value pair where the key is the codec_key and the value is the
    serialized object. During deserialization, the codec_key will be used to
    identify the appropriate codec.

    Args:
        - register_type (Type): If supplied, the JSONCodec will not only be
            registered, but automatically applied to the supplied type when
            serializing to JSON.

    Returns:
        - JSONCodec: the registered JSONCodec
    """

    def _register(register_type, codec_class: "JSONCodec") -> "JSONCodec":

        if CODEC_PREFIX + codec_class.codec_key in JSON_CODECS_KEYS:
            warnings.warn(
                'A JSONCodec was already registered for the codec_key "{}", '
                "and has been overwritten.".format(codec_class.codec_key)
            )
        JSON_CODECS_KEYS[CODEC_PREFIX + codec_class.codec_key] = codec_class

        # register the dispatch type
        if register_type:
            if isinstance(register_type, type):
                register_type = [register_type]
            for r_type in register_type:
                get_json_codec.register(r_type)(lambda obj: codec_class)

        return codec_class

    return partial(_register, register_type)


@singledispatch
def get_json_codec(obj: object) -> Optional["JSONCodec"]:  # pylint: disable=W0613
    return None


class JSONCodec(Generic[O, J]):
    """
    JSON Codecs define how to serialize objects and deserialize objects to JSON.

    Each codec has a unique key. When an object is wrapped in a codec, it
    is serialized as {codec.codec_key: codec(obj).serialize()}.

    When JSON objects are decoded, the key is matched and codec.deserialize() is
    called on the resulting value.
    """

    codec_key = ""  # type: str

    def __init__(self, value: O) -> None:
        if not self.codec_key:
            raise ValueError("This JSONCodec class has no codec key set.")
        self.value = value

    def serialize(self) -> J:
        """
        Serializes an object to a JSON-compatible type (str, dict, list, tuple).
        """
        raise NotImplementedError()

    @staticmethod
    def deserialize(obj: J) -> O:
        """
        Deserialize an object.
        """
        raise NotImplementedError()

    def __json__(self) -> Dict[str, J]:
        """
        Called by the JSON encoder in order to transform this object into
        a serializable dictionary. By default it returns
        {self.codec_key: self.serialize()}
        """
        return {CODEC_PREFIX + self.codec_key: self.serialize()}

    def __eq__(self, other: Any) -> bool:
        return type(self) == type(other) and self.value == other.value


@register_json_codec(set)
class SetCodec(JSONCodec[set, list]):
    """
    Serialize/deserialize sets
    """

    codec_key = "set"

    def serialize(self) -> list:
        return list(self.value)

    @staticmethod
    def deserialize(obj: list) -> set:
        return set(obj)


@register_json_codec(bytes)
class BytesCodec(JSONCodec[bytes, str]):
    """
    Serialize/deserialize bytes
    """

    codec_key = "b"

    def serialize(self) -> str:
        return binascii.b2a_base64(self.value).decode()

    @staticmethod
    def deserialize(obj: str) -> bytes:
        return binascii.a2b_base64(obj)


@register_json_codec(uuid.UUID)
class UUIDCodec(JSONCodec[uuid.UUID, str]):
    """
    Serialize/deserialize UUIDs
    """

    codec_key = "uuid"

    def serialize(self) -> str:
        return str(self.value)

    @staticmethod
    def deserialize(obj: str) -> uuid.UUID:
        return uuid.UUID(obj)


@register_json_codec(datetime.datetime)
class DateTimeCodec(JSONCodec[datetime.datetime, str]):
    """
    Serialize/deserialize DateTimes
    """

    codec_key = "datetime"

    def serialize(self) -> str:
        return self.value.isoformat()

    @staticmethod
    def deserialize(obj: str) -> datetime.datetime:
        return dateutil.parser.parse(obj)


@register_json_codec(datetime.date)
class DateCodec(JSONCodec[datetime.date, str]):
    """
    Serialize/deserialize Dates
    """

    codec_key = "date"

    def serialize(self) -> str:
        return self.value.isoformat()

    @staticmethod
    def deserialize(obj: str) -> datetime.date:
        return dateutil.parser.parse(obj).date()


@register_json_codec(datetime.timedelta)
class TimeDeltaCodec(JSONCodec[datetime.timedelta, float]):
    """
    Serialize/deserialize TimeDeltas
    """

    codec_key = "timedelta"

    def serialize(self) -> float:
        return self.value.total_seconds()

    @staticmethod
    def deserialize(obj: float) -> datetime.timedelta:
        return datetime.timedelta(seconds=obj)


@register_json_codec((type, types.FunctionType, types.BuiltinFunctionType))
class LoadObjectCodec(
    JSONCodec[Union[type, types.FunctionType, types.BuiltinFunctionType], str]
):
    """
    Serialize/deserialize objects by referencing their fully qualified name. This doesn't
    actually "serialize" them; it just serializes a reference to the already-existing object.

    Objects must already be imported at the same module path or deserialization will fail.
    """

    codec_key = "load_obj"

    def serialize(self) -> str:
        return to_qualified_name(self.value)

    @staticmethod
    def deserialize(obj: str) -> Type:
        return from_qualified_name(obj)


@register_json_codec()
class ObjectInitArgsCodec(JSONCodec[object, dict]):
    """
    Serializes an object by storing its class and a dict of initialization args.

    The initialization args can be collected from these places in sequence:
        1. an "_init_args" attribute storing a dict of args.
        3. an underscore-prefixed attribute with same name as the arg
        4. an attribute with the same name as the arg

    For example:

        class Foo:
            def __init__(a, b, c, **kwargs):
                self.a = a
                self._b = b
                self._kwargs = kwargs
                self._init_args = dict(c=c)
    """

    codec_key = "obj_init"

    def serialize(self) -> dict:

        init_args = {}

        signature = inspect.signature(self.value.__init__)  # type: ignore
        for arg, param in signature.parameters.items():

            # see if the init arg was stored in the _init_args dict
            if arg in getattr(self.value, "_init_args", {}):
                init_arg = self.value._init_args[arg]

            # check for an underscore-prefixed attribute with the same name
            elif hasattr(self.value, "_" + arg):
                init_arg = getattr(self.value, "_" + arg)

            # check for an attribute with the same name
            elif hasattr(self.value, arg):
                init_arg = getattr(self.value, arg)

            # default for var_positional
            elif param.kind == param.VAR_POSITIONAL:
                init_arg = ()

            # default for var_keyword
            elif param.kind == param.VAR_KEYWORD:
                init_arg = {}

            # fail
            else:
                raise ValueError(
                    'Could not find a value for the required init arg "{a}" of '
                    "object {o}. The value should be stored in an attribute "
                    "with the same name as the argument, optionally prefixed "
                    "with an underscore, or an _init_args dict "
                    "attribute.".format(a=arg, o=self.value)
                )

            if param.kind == param.VAR_KEYWORD:
                init_args["**kwargs"] = init_arg
            elif param.kind == param.VAR_POSITIONAL:
                init_args["*args"] = init_arg
            else:
                init_args[arg] = init_arg

        return dict(type=type(self.value), args=init_args)

    @staticmethod
    def deserialize(obj: dict) -> object:
        cls = obj["type"]
        kwargs = obj["args"].pop("**kwargs", {})
        args = obj["args"].pop("*args", ())
        kwargs.update(obj["args"])
        return cls(*args, **kwargs)


@register_json_codec()
class ObjectAttributesCodec(JSONCodec[object, dict]):
    """
    Serializes an object by storing its class name and a dict of attributes,
    similar to how the builtin copy module works. If the attributes_list is
    None (default), then the object's __dict__ is serialized. Otherwise, each
    provided attribute is stored and restored.

    The object's class *must* be imported before the object is deserialized.
    """

    codec_key = "obj_attrs"

    def __init__(self, value: Any, attributes_list: list = None) -> None:
        super().__init__(value)
        if attributes_list is None:
            attributes_list = list(value.__dict__.keys())
        self.attrs = attributes_list

    def serialize(self) -> dict:
        return dict(
            type=type(self.value), attrs={a: getattr(self.value, a) for a in self.attrs}
        )

    @staticmethod
    def deserialize(obj: dict) -> object:
        instance = object.__new__(obj["type"])
        instance.__dict__.update(obj["attrs"])
        return instance


class Serializable:
    """
    A class that automatically uses a specified JSONCodec to serialize itself.
    """

    _json_codec = ObjectAttributesCodec  # type: Type[JSONCodec]

    def __json__(self) -> JSONCodec:
        return self._json_codec(value=self)


class PrefectJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any):
        """
        Recursive method called when encoding JSON objects

            - Any class with a __json__() method is stored as the result of
                calling that method.
            - If no __json__ method is found, a JSON codec is applied via
                single dispatch.
            - Otherwise the original json encoding is used.
        """
        # call __json__ method if it exists
        if hasattr(obj, "__json__") and not isinstance(obj, type):
            return obj.__json__()

        # otherwise try to apply a json codec by dispatching on type
        # issue with singledispatch and pylint: https://github.com/PyCQA/pylint/issues/2155
        obj_codec = get_json_codec(obj)  # pylint: disable=E1128
        if obj_codec:
            return obj_codec(obj).__json__()  # pylint: disable=E1102

        else:
            return json.JSONEncoder.default(self, obj)


class PrefectJSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, object_hook=self.object_hook, **kwargs)

    def object_hook(self, dct):
        # iterate over the dictionary looking for a key that matches a codec.
        # it would be extremely unusual to have more than one such key.
        for key, value in dct.items():
            codec = JSON_CODECS_KEYS.get(key, None)
            if codec:
                full_codec_key = CODEC_PREFIX + codec.codec_key
                return codec.deserialize(dct[full_codec_key])

        return dct


dumps = partial(json.dumps, cls=PrefectJSONEncoder)
loads = partial(json.loads, cls=PrefectJSONDecoder)
