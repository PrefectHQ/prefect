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

    @classmethod
    def __from_json__(cls, obj):
        """
        Called by the JSON decoder when this codec's key is encountered. By
        default it calls the codec's deserialize method on the value associated
        with the codec key.
        """
        return cls.deserialize(obj[cls.codec_key])

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
class ImportableFunctionCodec(JSONCodec):

    def __init__(self, value):
        if not isinstance(value, types.FunctionType):
            raise SerializationError(
                'Only functions can apply ImportableFunctionCodec')
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


@register_JSONCodec('__encrypted_pickle__')
class SerializedEncryptedPickleCodec(JSONCodec):

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


class RegisteredSerializedCodec(JSONCodec):

    def __init__(self, value):
        if serialized_name(value) not in SERIALIZED_CLASS_REGISTRY:
            raise TypeError(
                'This class was not properly registered for serialization.')

        super().__init__(value=value)

    def serialize(self):
        return {
            '__class__': serialized_name(self.value),
            '__prefect_version__': prefect.__version__,
        }

    @classmethod
    def deserialize(self, obj):
        obj_class = SERIALIZED_CLASS_REGISTRY[obj.pop('__class__')]
        return obj_class

    @classmethod
    def __from_json__(cls, obj):
        """
        The JSON Decoder will call the deserialize() method on the appropriate
        value of the object, then call the object's after_deserialize method.
        """
        instance = super().__from_json__(obj)
        instance.after_deserialize(obj)
        return instance


@register_JSONCodec('__serialized_dict__')
class SerializedDictCodec(RegisteredSerializedCodec):
    """
    Serializes an object by storing its class name and __dict__, similar to how
    the builtin copy module works. The object is deserialized by creating a
    new instance of its class, and applying the serialized __dict__.
    """

    def __init__(self, value):
        if not isinstance(value, Serializable):
            raise TypeError('Value must subclass Serializable')
        super().__init__(value)

    def serialize(self):
        serialized = super().serialize()
        serialized_dict = self.value.__dict__.copy()
        for key in self.value._ignore_serialize_keys:
            serialized_dict.pop(key, None)
        if serialized_dict:
            serialized.update({'__dict__': serialized_dict})
        return serialized

    @classmethod
    def deserialize(cls, obj):
        obj_class = super().deserialize(obj)
        instance = object.__new__(obj_class)
        instance.__dict__.update(obj.pop('__dict__', {}))
        return instance


@register_JSONCodec('__serialized_init_args__')
class SerializedInitArgsCodec(RegisteredSerializedCodec):

    def __init__(self, value):
        if not isinstance(value, SerializableFromInitArgs):
            raise TypeError('Value must subclass SerializableFromInitArgs')
        super().__init__(value)

    def serialize(self):
        """
        Return a JSON-serializable dictionary that can be reconstructed as this object.
        """

        serialized = super().serialize()
        init_args = self.value._serialized_init_args
        if init_args:
            serialized.update({'__init_args__': init_args})
        return serialized

    @classmethod
    def deserialize(cls, obj):
        obj_class = super().deserialize(obj)
        init_args = obj.pop('__init_args__', {})
        args = init_args.pop('*args', ())
        kwargs = init_args.pop('**kwargs', {})
        return obj_class(**init_args, **kwargs)


class SerializableMetaclass(type):

    def __new__(meta, name, bases, class_dict):
        cls = type.__new__(meta, name, bases, class_dict)
        SERIALIZED_CLASS_REGISTRY[serialized_name(cls)] = cls
        return cls


class Serializable(metaclass=SerializableMetaclass):
    """
    A class that can be serialized to JSON by recording its __dict__.

    This will not work for objects that have unserializable attributes. Either
    exclude those attributes with the _ignore_serialize_keys class attribute,
    or consider an alternative serialization like SerializableFromInitArgs
    """

    _serialize_codec = SerializedDictCodec
    _ignore_serialize_keys = []

    def __eq__(self, other):
        return type(self) == type(other) and self.__json__() == other.__json__()

    def serialize(self):
        """
        A JSON-serializable description of the object that will be passed to
        """
        return {}

    @classmethod
    def deserialize(cls, obj):
        if not isinstance(obj, str):
            obj = json.dumps(obj)
        return json.loads(obj)

    def after_deserialize(self, details):
        """
        Called after deserializing an object.
        """
        pass

    def __json__(self):
        serialized = self.serialize()
        serialized.update(self._serialize_codec(self).__json__())
        return serialized


class SerializableFromInitArgs(Serializable):
    """
    A class that can be serialized to JSON by recording its instantiation
    arguments. The class is deserialized by creating a new class with the same
    arguments. This method of serialization is not as robust as Serializable,
    which copies the entire __dict__ of an object, but it may be preferable
    for certain situations where attributes are complicated or unserializable.
    """
    _serialize_codec = SerializedInitArgsCodec

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)

        # we wrap this in a try block because there are times when __new__
        # is called without any arguments, and we want to handle them - for
        # example, copy.copy() creates a new object and then copies all
        # attributes
        # try:
        self = object()
        signature = inspect.signature(cls.__init__)
        bound = signature.bind_partial(self, *args, **kwargs)
        # except Exception:
        #     return instance

        callargs = dict(bound.arguments)

        # identify the argument corresponding to 'self'
        self_arg = prefect.utilities.functions.get_first_arg(cls.__init__)
        if self_arg:
            callargs.pop(self_arg, None)

        # identify the argument corresponding to **kwargs
        var_k = prefect.utilities.functions.get_var_kw_arg(cls.__init__)
        if var_k:
            callargs['**kwargs'] = callargs.pop(var_k, {})

        # identify the argument corresponding to *args
        var_a = prefect.utilities.functions.get_var_pos_arg(cls.__init__)
        if var_a:
            # callargs['*args'] = callargs.pop(var_a, ())
            raise SerializationError(
                'Serializable classes do not support *args in __init__, '
                'because all arguments must be serializable with a known '
                'keyword. Consider replacing *args with an explicit sequence.')

        instance._serialized_init_args = callargs
        return instance

    # define __init__ because otherwise the *args and **kwargs of __new__
    # will be used as the signature
    def __init__(self):
        pass


def serializable(fn):
    """
    Decorator for marking a function as serializable.

    Note that this works by importing the function at the time of
    deserialization, so it may not be stable across software versions.
    """
    fn.__json__ = ImportableFunctionCodec(fn).__json__
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
            return codec.__from_json__(dct)

    return dct


# Monkey-patch the builtin JSON module with new serialization features
json.JSONEncoder.default = _json_encoder_fn
json._default_decoder = json.JSONDecoder(object_hook=_json_decoder_fn)


def load_raw_json(serialized):
    """
    Load JSON as a dict with no modifications
    """
    return json.loads(serialized, object_hook=lambda j: j)


def load_json_pickles(serialized, safe=True):

    def _pickle_decoder_fn(dct):
        if SerializedEncryptedPickleCodec.codec_key in dct:
            return SerializedEncryptedPickleCodec.unsafe_deserialize(
                dct[SerializedEncryptedPickleCodec.codec_key])
        else:
            return _json_decoder_fn(dct)

    if safe:
        return serialized
    else:
        return json.loads(serialized, object_hook=_pickle_decoder_fn)
