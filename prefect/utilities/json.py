"""
Facilities for serializing/deserializing Python objects to (safe) JSON.

Recursive function called when decoding objects from JSON:
    - '__datetime__' keys are restored as DateTimes
    - '__timedelta__' keys are restored as TimeDeltas
    - '__bytes__' keys are restored as bytes
    - '__import__' keys are restored by importing the referenced object
    - '__encrypted__' keys are decrypted using a local encryption key

"""
from functools import singledispatch
import base64
import datetime
import importlib
import json
import types
import uuid

import dateutil.parser
from cryptography.fernet import Fernet
import prefect
from prefect.signals import SerializationError

JSON_CODECS_KEYS = dict()
SERIALIZED_NAME_REGISTRY = dict()


def serialized_name(obj):
    if hasattr(obj, '__name__'):
        return obj.__module__ + '.' + obj.__name__
    else:
        return serialized_name(type(obj))


def import_serialized_name(serialized_name):
    if serialized_name in SERIALIZED_NAME_REGISTRY:
        return SERIALIZED_NAME_REGISTRY[serialized_name]
    else:
        module, name = serialized_name.rsplit('.', 1)
        if not module.startswith('prefect'):
            raise TypeError('Only Prefect objects may be marked importable.')
        try:
            return getattr(importlib.import_module(module), name)
        except AttributeError:
            raise SerializationError(
                "Could not import '{name}' from module '{module}'".format(
                    name=name, module=module))


def register_json_codec(codec_key):
    """
    Decorator that registers a JSON Codec to a corresponding codec_key.

    Whenever the codec is used to serialize an object, the result will be a
    key-value pair where the key is the codec_key and the value is the
    serialized object. During deserialization, the codec_key will be used to
    identify the appropriate codec.
    """

    def _register(codec_class):
        if codec_key in JSON_CODECS_KEYS or getattr(codec_class, 'codec_key'):
            raise ValueError(
                'A JSON codec is registered for codec_key "{}"'.format(
                    codec_key))
        codec_class.codec_key = codec_key
        JSON_CODECS_KEYS[codec_key] = codec_class
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

    @classmethod
    def deserialize(self, obj):
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
    def deserialize(self, obj):
        key = prefect.config.get('security', 'encryption_key')
        decrypted = Fernet(key).decrypt(obj.encode())
        decoded = base64.b64decode(decrypted).decode()
        return json.loads(decoded)


@register_json_codec('__set__')
@dispatch_json_codec.register(set)
class SetCodec(JSONCodec):

    def serialize(self):
        return list(self.value)

    @classmethod
    def deserialize(self, obj):
        return set(obj)


@register_json_codec('__bytes__')
@dispatch_json_codec.register(bytes)
class BytesCodec(JSONCodec):

    def serialize(self):
        return self.value.decode()

    @classmethod
    def deserialize(self, obj):
        return obj.encode()


@register_json_codec('__uuid__')
@dispatch_json_codec.register(uuid.UUID)
class UUIDCodec(JSONCodec):

    def serialize(self):
        return str(self.value)

    @classmethod
    def deserialize(self, obj):
        return uuid.UUID(obj)


@register_json_codec('__datetime__')
@dispatch_json_codec.register(datetime.datetime)
class DateTimeCodec(JSONCodec):

    def serialize(self):
        return self.value.isoformat()

    @classmethod
    def deserialize(self, obj):
        return dateutil.parser.parse(obj)


@register_json_codec('__timedelta__')
@dispatch_json_codec.register(datetime.timedelta)
class TimeDeltaCodec(JSONCodec):

    def serialize(self):
        return self.value.total_seconds()

    @classmethod
    def deserialize(self, obj):
        return datetime.timedelta(seconds=obj)


@register_json_codec('__import__')
@dispatch_json_codec.register(type)
@dispatch_json_codec.register(types.FunctionType)
class ImportableCodec(JSONCodec):

    def serialize(self):
        name = serialized_name(self.value)
        import_serialized_name(name)
        return dict(name=name, prefect_version=prefect.__version__)

    @classmethod
    def deserialize(self, obj):
        return import_serialized_name(obj['name'])


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
        # call __json__ method
        if hasattr(obj, '__json__') and not isinstance(obj, type):
            return obj.__json__()

        # otherwise try to apply a json codec by dispatching on type
        elif dispatch_json_codec(obj):
            return self.default(dispatch_json_codec(obj))

        else:
            return super().default(obj)


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


# Monkey-patch the builtin JSON module with new serialization features
json.JSONEncoder.default = PrefectJSONEncoder.default
json._default_encoder = PrefectJSONEncoder()
json._default_decoder = PrefectJSONDecoder()

# def load_json_pickles(serialized, safe=True):

#     def _pickle_decoder_fn(dct):
#         if SerializedEncryptedPickleCodec.codec_key in dct:
#             return SerializedEncryptedPickleCodec.unsafe_deserialize(
#                 dct[SerializedEncryptedPickleCodec.codec_key])
#         else:
#             return _json_decoder_fn(dct)

#     if safe:
#         return serialized
#     else:
#         return json.loads(serialized, object_hook=_pickle_decoder_fn)
