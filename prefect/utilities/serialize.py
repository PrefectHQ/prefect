from functools import partial
import base64
import datetime
import hashlib
import importlib
import inspect
import json
import types

import cloudpickle
import dateutil.parser
from cryptography.fernet import Fernet
import prefect
from prefect.signals import SerializationError

__all__ = [
    'Serializable',
    'serializeable',
    'SerializeMethod',
]

CLASS_REGISTRY = dict()


class SerializeMethod:
    INIT_ARGS = 'INIT_ARGS'
    PICKLE = 'PICKLE'
    FILE = 'FILE'


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


class SerializableMetaclass(type):

    def __new__(meta, name, bases, class_dict):
        cls = type.__new__(meta, name, bases, class_dict)
        CLASS_REGISTRY[serialized_name(cls)] = cls
        return cls


class Serializable(metaclass=SerializableMetaclass):
    """
    A class that can automatically be serialized to JSON and deserialized later.

    When the class type is created, it registers itself so that Prefect knows
    how to instantiate it. When an instance is created, it records the arguments
    that were used to create it. On deserialization, the correct class type is
    instantiated with those same arguments.
    """

    serialize_method = SerializeMethod.INIT_ARGS

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
        callargs['**kwargs'] = callargs.pop(var_k, {})

        # identify the argument corresponding to *args
        var_a = next((k for k, p in params if p.kind == p.VAR_POSITIONAL), None)
        if var_a:
            raise SerializationError(
                'Serializable classes do not support *args in __init__, '
                'because all arguments must be serializable with a known '
                'keyword. Consider replacing *args with an explicit sequence.')
        callargs['*args'] = callargs.pop(var_a, ())

        instance._init_args = callargs
        return instance

    # create __init__ because otherwise the __new__ signature is used for init.
    def __init__(self):
        pass

    def serialize(self):
        """
        Return a JSON-serializable dictionary representing this object.
        """
        # serialize the class
        if self.serialize_method == SerializeMethod.INIT_ARGS:
            serialized = {
                'method': SerializeMethod.INIT_ARGS,
                'class': serialized_name(type(self)),
                'init_args': Encrypted(self._init_args),
                'prefect_version': prefect.__version__,
            }

        elif self.serialize_method == SerializeMethod.PICKLE:
            serialized = {
                'method': SerializeMethod.PICKLE,
                'pickle': serialize_to_encrypted_pickle(self)
            }

        elif self.serialize_method == SerializeMethod.FILE:
            raise NotImplementedError()

        else:
            raise ValueError(
                'Unrecognized serialization method: "{}"'.format(
                    self.serialize_method))

        serialized = {'__serialized__': serialized}

        return serialized

    def __json__(self):
        """
        Return a JSON-serializable dictionary representing this object.

        By default, this calls self.serialize()
        """
        return self.serialize()

    @classmethod
    def deserialize(cls, serialized):
        return json.loads(serialized)


class Encrypted(Serializable):

    def __init__(self, value):
        self.value = value

    def serialize(self):
        key = prefect.config.get('security', 'encryption_key')
        payload = base64.b64encode(json.dumps(self.value).encode())
        return {'__encrypted__': Fernet(key).encrypt(payload).decode()}


def serializable(fn):
    """
    Decorator for marking a function as serializable.

    Note that this works by importing the function at the time of
    deserialization, so it may not be stable across software versions.
    """
    if not isinstance(fn, types.FunctionType):
        raise SerializationError('Only functions can be serialized this way.')
    fn.__json__ = lambda: {'__importable__': serialized_name(fn)}
    return fn


_encode_json_original = json.JSONEncoder.default


def _json_encoder_fn(self, obj):
    """
    Recursive function called when encoding JSON objects

        - Any class with a __json__() method is stored as the result of
            calling that method. Classes that subclass Serializable will
            encode the information needed to reinstantiate themselves.
        - DateTimes are stored as timestamps with the key '__datetime__'
        - TimeDeltas are stored as total seconds with the key '__timedelta__'
        - Bytes are stored as strings with the key '__bytes__'
    """

    # call __json__ method
    if hasattr(obj, '__json__'):
        return obj.__json__()

    # encode datetimes
    elif isinstance(obj, datetime.datetime):
        return {'__datetime__': obj.isoformat()}

    # encode timedeltas
    elif isinstance(obj, datetime.timedelta):
        return {'__timedelta__': obj.total_seconds()}

    # encode bytes
    elif isinstance(obj, bytes):
        return {'__bytes__': obj.decode()}

    # fallback on default
    else:
        return _encode_json_original(self, obj)


def _json_decoder_fn(dct, safe=True):
    """

    If safe = True, then JSON objects serialized as pickles will NOT be
        deserialized. If safe = False, they will be.

    Recursive function called when decoding objects from JSON:
        - '__serialized__' objects are instantiated correctly but not unpickled
        - '__datetime__' keys are restored as DateTimes
        - '__timedelta__' keys are restored as TimeDeltas
        - '__bytes__' keys are restored as bytes
        - '__importable__' keys are restored by importing the referenced object
        - '__encrypted__' keys are decrypted using a local encryption key

    """
    # decrypt
    if '__encrypted__' in dct:
        key = prefect.config.get('security', 'encryption_key')
        decrypted = Fernet(key).decrypt(dct['__encrypted__'].encode())
        decoded = base64.b64decode(decrypted).decode()
        return _json_decoder_fn(json.loads(decoded))

    # decode datetimes
    if '__datetime__' in dct:
        return dateutil.parser.parse(dct['__datetime__'])

    # decode timestamps
    if '__timedelta__' in dct:
        return datetime.timedelta(seconds=dct['__timedelta__'])

    # decode bytes:
    if '__bytes__' in dct:
        return dct['__bytes__'].encode()

    # decode functions
    if '__importable__' in dct:
        module, name = dct['__importable__'].rsplit('.', 1)
        try:
            return getattr(importlib.import_module(module), name)
        except AttributeError:
            raise SerializationError(
                "Could not import '{name}' from module '{module}'".format(
                    name=name, module=module))

    # decode Serialized objects
    if '__serialized__' in dct:
        serialized = dct['__serialized__']

        if serialized.get('method') == SerializeMethod.INIT_ARGS:
            cls = CLASS_REGISTRY[serialized['class']]
            init_args = serialized.get('init_args', {})
            args = init_args.pop('*args', ())
            kwargs = init_args.pop('**kwargs', {})
            return cls(**init_args, **kwargs)

        elif serialized.get('method') == SerializeMethod.PICKLE:
            if safe:
                return dct
            else:
                key = prefect.config.get('security', 'encryption_key')
                return deserialize_from_encrypted_pickle(
                    serialized['pickle'], encryption_key=key)

    return dct


# Monkey-patch the builtin JSON module with new serialization features
json.JSONEncoder.default = _json_encoder_fn
json._default_decoder = json.JSONDecoder(
    object_hook=partial(_json_decoder_fn, safe=True))


def load_json(serialized, safe=True):
    """
    Load Prefect-flavored JSON serializations.

    If safe is False, then pickles will be unpickled. Don't do this unless
    you're sure you know what you're doing.
    """
    # decoder = json.JSONDecoder(
    #     object_hook=)
    return json.loads(
        serialized, object_hook=partial(_json_decoder_fn, safe=safe))
