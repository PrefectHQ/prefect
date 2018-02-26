"""
Facilities for serializing/deserializing Python objects to (safe) JSON.

Recursive function called when decoding objects from JSON:
    - '__serialized__' objects are instantiated correctly but not unpickled
    - '__datetime__' keys are restored as DateTimes
    - '__timedelta__' keys are restored as TimeDeltas
    - '__bytes__' keys are restored as bytes
    - '__importable__' keys are restored by importing the referenced object
    - '__encrypted__' keys are decrypted using a local encryption key

"""
from functools import partial, singledispatch
import base64
import datetime
import importlib
import inspect
import json
import types
import uuid

import cloudpickle
import dateutil.parser
from cryptography.fernet import Fernet
import prefect
from prefect.signals import SerializationError

__all__ = [
    'Encrypted',
    'Serializable',
    'serializable',
]

JSON_CODECS = dict()
SERIALIZED_CLASS_REGISTRY = dict()


def serialized_name(obj):
    if hasattr(obj, '__name__'):
        return obj.__module__ + '.' + obj.__name__
    else:
        return serialized_name(type(obj))


def serialize_to_encrypted_pickle(obj, encryption_key=None):
    """
    Serialize a Python object, optionally encrypting the result with a key

    Args:
        obj (object): The object to serialize
        encryption_key (str): key used to encrypt the serialization
    """
    if encryption_key is None:
        encryption_key = prefect.config.get('security', 'encryption_key')
    if not encryption_key:
        raise ValueError("Encryption key not set.")
    serialized = base64.b64encode(cloudpickle.dumps(obj))
    serialized = Fernet(encryption_key).encrypt(serialized).decode()
    return serialized


def deserialize_from_encrypted_pickle(serialized, encryption_key=None):
    """
    Deserialized a Python object.

    Args:
        serialized (bytes): serialized Prefect object
        encryption_key (str): key used to decrypt the serialization
    """
    if encryption_key is None:
        encryption_key = prefect.config.get('security', 'encryption_key')
    if not encryption_key:
        raise ValueError("Encryption key not set.")
    if isinstance(serialized, str):
        serialized = serialized.encode()
    serialized = Fernet(encryption_key).decrypt(serialized).decode()
    return cloudpickle.loads(base64.b64decode(serialized))


def register_JSONCodec(key):

    def _register(codec, codec_key):
        JSON_CODECS[codec_key] = codec
        codec.codec_key = key
        return codec

    return partial(_register, codec_key=key)


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
        return obj

    def __json__(self):
        return {self.codec_key: self.serialize()}

    def __eq__(self, other):
        return type(self) == type(other) and self.value == other.value


@singledispatch
def apply_json_codec(obj):
    return None


@register_JSONCodec('__encrypted__')
class Encrypted(JSONCodec):

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


@register_JSONCodec('__set__')
@apply_json_codec.register(set)
class SetCodec(JSONCodec):

    def serialize(self):
        return list(self.value)

    @classmethod
    def deserialize(cls, obj):
        return set(obj)


@register_JSONCodec('__bytes__')
@apply_json_codec.register(bytes)
class BytesCodec(JSONCodec):

    def serialize(self):
        return self.value.decode()

    @classmethod
    def deserialize(cls, obj):
        return obj.encode()


@register_JSONCodec('__uuid__')
@apply_json_codec.register(uuid.UUID)
class UUIDCodec(JSONCodec):

    def serialize(self):
        return str(self.value)

    @classmethod
    def deserialize(cls, obj):
        return uuid.UUID(obj)


@register_JSONCodec('__datetime__')
@apply_json_codec.register(datetime.datetime)
class DateTimeCodec(JSONCodec):

    def serialize(self):
        return self.value.isoformat()

    @classmethod
    def deserialize(cls, obj):
        return dateutil.parser.parse(obj)


@register_JSONCodec('__timedelta__')
@apply_json_codec.register(datetime.timedelta)
class TimeDeltaCodec(JSONCodec):

    def serialize(self):
        return self.value.total_seconds()

    @classmethod
    def deserialize(cls, obj):
        return datetime.timedelta(seconds=obj)


@register_JSONCodec('__importable_fn__')
class ImportableFunction(JSONCodec):

    def __init__(self, value):
        if not isinstance(value, types.FunctionType):
            raise SerializationError(
                'Only functions can be marked as ImportableFunction')
        super().__init__(value=value)

    def serialize(self):
        return serialized_name(self.value)

    @classmethod
    def deserialize(cls, obj):
        module, name = obj.rsplit('.', 1)
        try:
            return getattr(importlib.import_module(module), name)
        except AttributeError:
            raise SerializationError(
                "Could not import '{name}' from module '{module}'".format(
                    name=name, module=module))


# @register_JSONCodec('__json_serialized__')
# class JSONSerialized(JSONCodec):

#     def serialize(self):
#         return self.value

#     @classmethod
#     def deserialize(cls, obj):
#         return obj


@register_JSONCodec('__encrypted_pickle__')
class EncryptedPickle(JSONCodec):

    def serialize(self):
        return {
            'pickle': serialize_to_encrypted_pickle(self.value),
            'prefect_version': prefect.__version__
        }

    @classmethod
    def deserialize(cls, obj):
        """
        We never automatically unpickle.

        Call json_unpickle(obj, safe=False) for that behavior.
        """
        return obj

    @classmethod
    def unsafe_deserialize(cls, obj):
        return deserialize_from_encrypted_pickle(obj['pickle'])


@register_JSONCodec('__serialized_init_args__')
class SerializedInitArgs(JSONCodec):

    def __init__(self, value):
        if not isinstance(value, Serializable):
            raise TypeError(
                'SerializedInitArgs object must subclass Serializable')
        super().__init__(value=value)

    def serialize(self):
        """
        Return a JSON-serializable dictionary representing this object.
        """

        serialized = self.value.serialize()

        serialized.update({
            '__class__': serialized_name(self.value),
            '__init_args__': getattr(self.value, '_serialized_init_args', {}),
            '__prefect_version__': prefect.__version__,
        })

        return serialized


    @classmethod
    def deserialize(cls, obj):
        cls = SERIALIZED_CLASS_REGISTRY[obj.pop('__class__')]
        init_args = obj.pop('__init_args__')
        args = init_args.pop('*args', ())
        kwargs = init_args.pop('**kwargs', {})
        instance = cls(**init_args, **kwargs)
        instance.after_deserialize(obj)
        return instance


class SerializableMetaclass(type):

    def __new__(meta, name, bases, class_dict):
        cls = type.__new__(meta, name, bases, class_dict)
        SERIALIZED_CLASS_REGISTRY[serialized_name(cls)] = cls
        return cls


class Serializable(metaclass=SerializableMetaclass):
    """
    A class that can automatically be serialized to JSON and deserialized later.

    When the class type is created, it registers itself so that Prefect knows
    how to instantiate it. When an instance is created, it records the arguments
    that were used to create it. On deserialization, the correct class type is
    instantiated with those same arguments.
    """

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)

        self = object()
        signature = inspect.signature(cls.__init__)
        bound = signature.bind(self, *args, **kwargs)

        callargs = dict(bound.arguments)

        # identify the argument corresponding to 'self'
        self_arg = next((k for k, a in callargs.items() if a is self), None)
        if self_arg:
            callargs.pop(self_arg, None)

        # identify the argument corresponding to **kwargs
        params = signature.parameters.items()
        var_k = next((k for k, p in params if p.kind == p.VAR_KEYWORD), None)
        if var_k:
            callargs['**kwargs'] = callargs.pop(var_k, {})

        # identify the argument corresponding to *args
        var_a = next((k for k, p in params if p.kind == p.VAR_POSITIONAL), None)
        if var_a:
            callargs['*args'] = callargs.pop(var_a, ())
            raise SerializationError(
                'Serializable classes do not support *args in __init__, '
                'because all arguments must be serializable with a known '
                'keyword. Consider replacing *args with an explicit sequence.')

        instance._serialized_init_args = callargs
        return instance

    # create __init__ because otherwise the __new__ signature is used for init.
    def __init__(self):
        pass

    def __eq__(self, other):
        if type(self) == type(other):
            return self.__json__() == other.__json__()
        return False

    def __json__(self):
        return SerializedInitArgs(self).__json__()

    def serialize(self):
        """
        A JSON-serializable description of the object that will be passed to
        """
        return {}

    @classmethod
    def deserialize(cls, serialized):
        if not isinstance(serialized, str):
            serialized = json.dumps(serialized)
        result = json.loads(serialized)
        if not isinstance(result, cls):
            raise TypeError(
                'Type mismatch between deserializing class and '
                'serialized class.')
        return result

    def after_deserialize(self, payload):
        """
        Called after deserializing an object.
        """
        pass


def serializable(fn):
    """
    Decorator for marking a function as serializable.

    Note that this works by importing the function at the time of
    deserialization, so it may not be stable across software versions.
    """
    fn.__json__ = ImportableFunction(fn).__json__
    return fn


_encode_json_original = json.JSONEncoder.default


def _json_encoder_fn(self, obj):
    """
    Recursive method called when encoding JSON objects

        - Any class with a __json__() method is stored as the result of
            calling that method.
        - If no __json__ method is found, a JSON codec is applied via
            single dispatch.
        - Otherwise the original json encoding is used.
    """

    # call __json__ method
    if hasattr(obj, '__json__'):
        return obj.__json__()

    # otherwise try to apply a json codec via singledispatch on type
    elif apply_json_codec(obj):
        return _json_encoder_fn(self, apply_json_codec(obj))

    # fallback on default
    else:
        return _encode_json_original(self, obj)


def _json_decoder_fn(dct):
    # iterate over the dictionary looking for a key that matches a codec.
    # it would be extremely unusual to have more than one such key.
    for key, value in dct.items():
        codec = JSON_CODECS.get(key, None)
        if codec:
            return codec.deserialize(value)

    return dct


# Monkey-patch the builtin JSON module with new serialization features
json.JSONEncoder.default = _json_encoder_fn
json._default_decoder = json.JSONDecoder(object_hook=_json_decoder_fn)


def load_json(serialized):
    """
    Load Prefect-flavored JSON serializations.
    """
    # decoder = json.JSONDecoder(
    #     object_hook=)
    return json.loads(serialized, object_hook=_json_decoder_fn)


def dump_json(obj):
    return json.dumps(obj)


def load_json_pickles(serialized, safe=True):

    def _pickle_decoder_fn(dct):
        if EncryptedPickle.codec_key in dct:
            return EncryptedPickle.unsafe_deserialize(
                dct[EncryptedPickle.codec_key])
        else:
            return _json_decoder_fn(dct)

    if safe:
        return serialized
    else:
        return json.loads(serialized, object_hook=_pickle_decoder_fn)
