"""
Facilities for serializing/deserializing Python objects to JSON.
"""
import sys
from functools import singledispatch
import base64
import datetime
import json
import types
import uuid
import inspect
import dateutil.parser
from cryptography.fernet import Fernet
import prefect
from typing import Type

JSON_CODECS_KEYS = dict()


def object_from_string(obj_str):
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


def qualified_name(obj):
    return obj.__module__ + "." + obj.__qualname__


def register_json_codec(codec_key, dispatch_type=None):
    """
    Decorator that registers a JSON Codec to a corresponding codec_key.

    If a dispatch_type is provided, the codec will automatically be applied
    to that type.

    Whenever the codec is used to serialize an object, the result will be a
    key-value pair where the key is the codec_key and the value is the
    serialized object. During deserialization, the codec_key will be used to
    identify the appropriate codec.
    """

    def _register(codec_class):

        # register the codec key
        if codec_key in JSON_CODECS_KEYS or getattr(codec_class, "codec_key"):
            raise ValueError(
                'A JSON codec is registered for codec_key "{}"'.format(codec_key)
            )
        codec_class.codec_key = codec_key
        JSON_CODECS_KEYS[codec_key] = codec_class

        # register the dispatch type
        if dispatch_type:
            dispatch_json_codec.register(dispatch_type)(codec_class)

        return codec_class

    return _register


@singledispatch
def dispatch_json_codec(obj):
    return None


class JSONCodec:
    """
    JSON Codecs define how to serialize objects and deserialize objects to JSON.

    Each codec has a unique key. When an object is wrapped in a codec, it
    is serialized as {codec.codec_key: codec(obj).serialize()}.

    When JSON objects are decoded, the key is matched and codec.deserialize() is
    called on the resulting value.
    """

    codec_key = None

    def __init__(self, value):
        self.value = value

    def serialize(self):
        """
        Returns the value that will be serialized using this JSONCodec's
        codec_key
        """
        return self.value

    @staticmethod
    def deserialize(obj):
        """
        Deserialize an object.
        """
        return obj

    def __json__(self):
        """
        Called by the JSON encoder in order to transform this object into
        a serializable dictionary. By default it returns
        {self.codec_key: self.serialize()}
        """
        return {self.codec_key: self.serialize()}

    def __eq__(self, other):
        return type(self) == type(other) and self.value == other.value


@register_json_codec("//set", dispatch_type=set)
class SetCodec(JSONCodec):
    """
    Serialize/deserialize sets
    """

    def serialize(self):
        return list(self.value)

    @staticmethod
    def deserialize(obj):
        return set(obj)


@register_json_codec("//b", dispatch_type=bytes)
class BytesCodec(JSONCodec):
    """
    Serialize/deserialize bytes
    """

    def serialize(self):
        return self.value.decode()

    @staticmethod
    def deserialize(obj):
        return obj.encode()


@register_json_codec("//uuid", dispatch_type=uuid.UUID)
class UUIDCodec(JSONCodec):
    """
    Serialize/deserialize UUIDs
    """

    def serialize(self):
        return str(self.value)

    @staticmethod
    def deserialize(obj):
        return uuid.UUID(obj)


@register_json_codec("//datetime", dispatch_type=datetime.datetime)
class DateTimeCodec(JSONCodec):
    """
    Serialize/deserialize DateTimes
    """

    def serialize(self):
        return self.value.isoformat()

    @staticmethod
    def deserialize(obj):
        return dateutil.parser.parse(obj)


@register_json_codec("//date", dispatch_type=datetime.date)
class DateCodec(JSONCodec):
    """
    Serialize/deserialize Dates
    """

    def serialize(self):
        return self.value.isoformat()

    @staticmethod
    def deserialize(obj):
        return dateutil.parser.parse(obj).date()


@register_json_codec("//timedelta", dispatch_type=datetime.timedelta)
class TimeDeltaCodec(JSONCodec):
    """
    Serialize/deserialize TimeDeltas
    """

    def serialize(self):
        return self.value.total_seconds()

    @staticmethod
    def deserialize(obj):
        return datetime.timedelta(seconds=obj)


@register_json_codec("//obj", dispatch_type=type)
class LoadObjectCodec(JSONCodec):
    """
    Serialize/deserialize objects by referencing their fully qualified name.

    Objects must already be imported at the same module path or
    deserialization will fail.
    """

    def serialize(self):
        return qualified_name(self.value)

    @staticmethod
    def deserialize(obj):
        return object_from_string(obj)


def serializable(fn):
    """
    Decorator that marks a function as automatically serializable via
    LoadObjectCodec
    """
    if hasattr(fn, "__json__"):
        raise ValueError("Object already has a __json__() method.")
    setattr(fn, "__json__", lambda: LoadObjectCodec(fn).__json__())
    return fn


@register_json_codec("//encrypted")
class EncryptedCodec(JSONCodec):
    def serialize(self):
        key = prefect.config.security.encryption_key
        payload = base64.b64encode(json.dumps(self.value).encode())
        return Fernet(key).encrypt(payload).decode()

    @staticmethod
    def deserialize(obj):
        key = prefect.config.security.encryption_key
        decrypted = Fernet(key).decrypt(obj.encode())
        decoded = base64.b64decode(decrypted).decode()
        return json.loads(decoded)


@register_json_codec("//obj_init")
class ObjectInitArgsCodec(JSONCodec):
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

    def serialize(self):

        init_args = {}

        signature = inspect.signature(self.value.__init__)
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
    def deserialize(obj):
        cls = obj["type"]
        kwargs = obj["args"].pop("**kwargs", {})
        args = obj["args"].pop("*args", ())
        return cls(*args, **obj["args"], **kwargs)


@register_json_codec("//obj_attrs")
class ObjectAttributesCodec(JSONCodec):
    """
    Serializes an object by storing its class name and a dict of attributes,
    similar to how the builtin copy module works. If the attributes_list is
    None (default), then the object's __dict__ is serialized. Otherwise, each
    provided attribute is stored and restored.

    The object's class *must* be imported before the object is deserialized.
    """

    def __init__(self, value, attributes_list=None):
        super().__init__(value)
        if attributes_list is None:
            attributes_list = list(value.__dict__.keys())
        self.attrs = attributes_list

    def serialize(self):
        return dict(
            type=type(self.value), attrs={a: getattr(self.value, a) for a in self.attrs}
        )

    @staticmethod
    def deserialize(obj):
        instance = object.__new__(obj["type"])
        instance.__dict__.update(obj["attrs"])
        return instance


class Serializable:
    """
    A class that automatically uses a specified JSONCodec to serialize itself.
    """

    _json_codec = ObjectInitArgsCodec  # type: Type[JSONCodec]

    def __json__(self):
        return self._json_codec(value=self)


class PrefectJSONEncoder(json.JSONEncoder):
    def default(self, obj):
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
        obj_codec = dispatch_json_codec(obj)
        if obj_codec:
            return obj_codec.__json__()

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
                return codec.deserialize(dct[codec.codec_key])

        return dct


json._default_encoder = PrefectJSONEncoder()
json._default_decoder = PrefectJSONDecoder()
