import functools
import base64
from Crypto.Cipher import AES
from Crypto import Random
import cloudpickle
import datetime
import hashlib
import json
import prefect

JSON_CLASS_REGISTRY = dict()

# -----------------------------------------------------------------------------
# monkey patch json.JSONEncoder to support:
# - datetime to timestamp
# - objects with __json__ methods

_original_encoder_default = json.JSONEncoder.default


def _default_encode(self, obj):
    if isinstance(obj, datetime.datetime):
        return obj.timestamp()
    elif type(obj) in JSON_CLASS_REGISTRY.values() or hasattr(obj, '__json__'):
        serialized = obj.__json__()
        if JSON_CLASS_REGISTRY.get(type(obj).__name__) is not type(obj):
            raise TypeError(
                'The serialized type was not registered with the '
                'JSON_CLASS_REGISTRY, or another class with the same name '
                'overwrote it. Decorate the class with @register_json.')
        serialized['__prefect_type__'] = type(obj).__name__
        return serialized
    else:
        return _original_encoder_default(self, obj)


json.JSONEncoder.default = _default_encode

# -----------------------------------------------------------------------------
# monkey patch json.JSONDecoder to support:
# - loading classes based on __prefect_type__
# - objects with __json__ methods


def _default_object_hook(dct):
    if '__prefect_type__' in dct:
        cls = JSON_CLASS_REGISTRY[dct.pop('__prefect_type__')]
        return cls(**dct)
    return dct


json._default_decoder = json.JSONDecoder(object_hook=_default_object_hook)


def register_json(cls):
    """
    Decorator to register a serialized class
    """

    name = cls.__name__
    if not hasattr(cls, '__json__'):
        raise ValueError('Class has no "__json__()" method.')
    JSON_CLASS_REGISTRY[name] = cls
    return cls


# -----------------------------------------------------------------------------


class AESCipher(object):
    """
    http://stackoverflow.com/a/21928790
    """

    def __init__(self, key):
        self.bs = 32
        self.key = hashlib.sha256(key.encode()).digest()

    def encrypt(self, raw):
        raw = self._pad(raw)
        iv = Random.new().read(AES.block_size)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return base64.b64encode(iv + cipher.encrypt(raw))

    def decrypt(self, enc):
        enc = base64.b64decode(enc)
        iv = enc[:AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return self._unpad(cipher.decrypt(enc[AES.block_size:])).decode('utf-8')

    def _pad(self, s):
        pad_chr = chr(self.bs - len(s) % self.bs)
        if isinstance(s, bytes):
            pad_chr = pad_chr.encode()
        return s + (self.bs - len(s) % self.bs) * pad_chr

    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s) - 1:])]


def serialize(obj, encryption_key=None):
    """
    Serialize a Python object, optionally encrypting the result with a key

    Args:
        obj (object): The object to serialize
        encryption_key (str): key used to encrypt the serialization
    """
    if encryption_key is None:
        encryption_key = prefect.config.get('prefect', 'encryption_key')
    serialized = base64.b64encode(cloudpickle.dumps(obj))
    if encryption_key:
        cipher = AESCipher(key=encryption_key)
        serialized = cipher.encrypt(serialized)
    if isinstance(serialized, bytes):
        serialized = serialized.decode()
    return serialized


def deserialize(serialized, encryption_key=None):
    """
    Deserialized a Python object.

    Args:
        serialized (bytes): serialized Prefect object
        encryption_key (str): key used to decrypt the serialization
    """
    if encryption_key is None:
        encryption_key = prefect.config.get('prefect', 'encryption_key')
    if isinstance(serialized, str):
        serialized = serialized.encode()
    if encryption_key:
        cipher = AESCipher(key=encryption_key)
        serialized = cipher.decrypt(serialized)
    return cloudpickle.loads(base64.b64decode(serialized))
