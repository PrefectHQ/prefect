"""
Facilities for serializing/deserializing Python objects to JSON.
"""
from functools import singledispatch
import base64
import datetime
import importlib
import json
import uuid

import dateutil.parser
from cryptography.fernet import Fernet
import prefect
from prefect.signals import SerializationError

JSON_CODECS_KEYS = dict()


def serialized_name(obj):
    if hasattr(obj, '__name__'):
        return obj.__module__ + '.' + obj.__name__
    else:
        return serialized_name(type(obj))


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


@register_json_codec('__encrypted__')
class EncryptedCodec(JSONCodec):

    def serialize(self):
        key = prefect.config.get('security', 'encryption_key')
        payload = base64.b64encode(json.dumps(self.value).encode())
        return Fernet(key).encrypt(payload).decode()

    @classmethod
    def deserialize(cls, obj):
        key = prefect.config.get('security', 'encryption_key')
        decrypted = Fernet(key).decrypt(obj.encode())
        decoded = base64.b64decode(decrypted).decode()
        return json.loads(decoded)


@register_json_codec('__set__', dispatch_type=set)
class SetCodec(JSONCodec):

    def serialize(self):
        return list(self.value)

    @classmethod
    def deserialize(cls, obj):
        return set(obj)


@register_json_codec('__bytes__', dispatch_type=bytes)
class BytesCodec(JSONCodec):

    def serialize(self):
        return self.value.decode()

    @classmethod
    def deserialize(cls, obj):
        return obj.encode()


@register_json_codec('__uuid__', dispatch_type=uuid.UUID)
class UUIDCodec(JSONCodec):

    def serialize(self):
        return str(self.value)

    @classmethod
    def deserialize(cls, obj):
        return uuid.UUID(obj)


@register_json_codec('__datetime__', dispatch_type=datetime.datetime)
class DateTimeCodec(JSONCodec):

    def serialize(self):
        return self.value.isoformat()

    @classmethod
    def deserialize(cls, obj):
        return dateutil.parser.parse(obj)


@register_json_codec('__date__', dispatch_type=datetime.date)
class DateTimeCodec(JSONCodec):

    def serialize(self):
        return self.value.isoformat()

    @classmethod
    def deserialize(cls, obj):
        return dateutil.parser.parse(obj).date()


@register_json_codec('__timedelta__', dispatch_type=datetime.timedelta)
class TimeDeltaCodec(JSONCodec):

    def serialize(self):
        return self.value.total_seconds()

    @classmethod
    def deserialize(cls, obj):
        return datetime.timedelta(seconds=obj)


# @register_json_codec('__import__')
# @get_json_codec.register(type)
# @get_json_codec.register(types.FunctionType)
# class ImportableCodec(JSONCodec):

#     def serialize(self):
#         name = serialized_name(self.value)
#         import_serialized_name(name)
#         return dict(name=name, prefect_version=prefect.__version__)

#     @classmethod
#     def deserialize(cls, obj):
#         return import_serialized_name(obj['name'])


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
        codec = get_json_codec(obj)
        if codec:
            return self.default(codec)

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
