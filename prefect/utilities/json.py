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

import dateutil.parser
from cryptography.fernet import Fernet
import prefect

JSON_CODECS_KEYS = dict()


def qualified_name(obj):
    return obj.__module__ + '.' + obj.__name__


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
        if codec_key in JSON_CODECS_KEYS or getattr(codec_class, 'codec_key'):
            raise ValueError(
                'A JSON codec is registered for codec_key "{}"'.format(
                    codec_key))
        codec_class.codec_key = codec_key
        JSON_CODECS_KEYS[codec_key] = codec_class

        # register the dispatch type
        if dispatch_type:
            get_json_codec.register(dispatch_type)(codec_class)

        return codec_class

    return _register


@singledispatch
def get_json_codec(obj):
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

    @classmethod
    def deserialize(cls, obj):
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


@register_json_codec('__set__', dispatch_type=set)
class SetCodec(JSONCodec):
    """
    Serialize/deserialize sets
    """

    def serialize(self):
        return list(self.value)

    @classmethod
    def deserialize(cls, obj):
        return set(obj)


@register_json_codec('__bytes__', dispatch_type=bytes)
class BytesCodec(JSONCodec):
    """
    Serialize/deserialize bytes
    """

    def serialize(self):
        return self.value.decode()

    @classmethod
    def deserialize(cls, obj):
        return obj.encode()


@register_json_codec('__uuid__', dispatch_type=uuid.UUID)
class UUIDCodec(JSONCodec):
    """
    Serialize/deserialize UUIDs
    """

    def serialize(self):
        return str(self.value)

    @classmethod
    def deserialize(cls, obj):
        return uuid.UUID(obj)


@register_json_codec('__datetime__', dispatch_type=datetime.datetime)
class DateTimeCodec(JSONCodec):
    """
    Serialize/deserialize DateTimes
    """

    def serialize(self):
        return self.value.isoformat()

    @classmethod
    def deserialize(cls, obj):
        return dateutil.parser.parse(obj)


@register_json_codec('__date__', dispatch_type=datetime.date)
class DateCodec(JSONCodec):
    """
    Serialize/deserialize Dates
    """

    def serialize(self):
        return self.value.isoformat()

    @classmethod
    def deserialize(cls, obj):
        return dateutil.parser.parse(obj).date()


@register_json_codec('__timedelta__', dispatch_type=datetime.timedelta)
class TimeDeltaCodec(JSONCodec):
    """
    Serialize/deserialize TimeDeltas
    """

    def serialize(self):
        return self.value.total_seconds()

    @classmethod
    def deserialize(cls, obj):
        return datetime.timedelta(seconds=obj)


@register_json_codec('__imported_object__')
class ImportedObjectCodec(JSONCodec):
    """
    Serialize/deserialize objects by referencing their fully qualified name.

    Objects must already be imported at the same module path or
    deserialization will fail.
    """

    def serialize(self):
        return dict(
            path=qualified_name(self.value),
            prefect_version=prefect.__version__)

    @classmethod
    def deserialize(cls, obj):
        obj_import_path = obj['path'].split('.')
        loaded_obj = sys.modules[obj_import_path[0]]
        for p in obj_import_path[1:]:
            loaded_obj = getattr(loaded_obj, p)
        return loaded_obj


def serializable(fn):
    """
    Decorator that marks a function as automatically serializable via
    ImportedObjectCodec
    """
    if hasattr(fn, '__json__'):
        raise ValueError('Object already has a __json__() method.')
    setattr(fn, '__json__', lambda: ImportedObjectCodec(fn).__json__())
    return fn


@register_json_codec('__encrypted__')
class EncryptedCodec(JSONCodec):

    def serialize(self):
        key = prefect.config.security.encryption_key
        payload = base64.b64encode(json.dumps(self.value).encode())
        return Fernet(key).encrypt(payload).decode()

    @classmethod
    def deserialize(cls, obj):
        key = prefect.config.security.encryption_key
        decrypted = Fernet(key).decrypt(obj.encode())
        decoded = base64.b64decode(decrypted).decode()
        return json.loads(decoded)


@register_json_codec('__object_attrs__')
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
        self.attributes_list = attributes_list

    def serialize(self):
        serialized = dict(
            type=ImportedObjectCodec(type(self.value)),
            attrs={a: getattr(self.value, a)
                   for a in self.attributes_list})
        return serialized

    @classmethod
    def deserialize(cls, obj):
        instance = object.__new__(obj['type'])
        instance.__dict__.update(obj['attrs'])
        return instance


class Serializable:
    """
    A class that automatically uses a specified JSONCodec to serialize itself.
    """
    json_codec = ObjectAttributesCodec
    json_attributes_list = None

    def __json__(self):
        return self.json_codec(
            value=self, attributes_list=self.json_attributes_list)

    @classmethod
    def deserialize(cls, serialized):
        obj = json.loads(serialized)
        if not issubclass(type(obj), cls):
            raise TypeError('Invalid type')
        return obj


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
        if hasattr(obj, '__json__') and not isinstance(obj, type):
            return obj.__json__()

        # otherwise try to apply a json codec by dispatching on type
        obj_codec = get_json_codec(obj)
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
