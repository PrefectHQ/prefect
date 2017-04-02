import base64
from collections import namedtuple
from Crypto.Cipher import AES
from Crypto import Random
import distributed
import hashlib
import prefect
import ujson


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
        return s + (self.bs - len(s) % self.bs) * chr(self.bs - len(s) % self.bs)

    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s)-1:])]


def serialize(obj, encryption_key=None):
    """
    Serialize a Python object, optionally encrypting the result with a key

    Args:
        obj (object): The object to serialize
        encryption_key (str): If provided, used to encrypt the serialization
    """
    header, frames = distributed.protocol.serialize(obj)
    serialized = ujson.dumps(
        dict(
            header=header,
            frames=[base64.b64encode(b).decode('utf-8') for b in frames]))
    if encryption_key is not None:
        cipher = AESCipher(key=encryption_key)
        serialized = cipher.encrypt(serialized)

    return serialized


def deserialize(serialized, decryption_key=None):
    """
    Deserialized a Python object.

    Args:
        decryption_key (str): If provided, used to decrypt the serialization.
    """
    if decryption_key is not None:
        cipher = AESCipher(key=decryption_key)
        serialized = cipher.decrypt(serialized)
    serialized = ujson.loads(serialized)
    header, frames = serialized['header'], serialized['frames']
    frames = [base64.b64decode(b.encode('utf-8')) for b in frames]
    return distributed.protocol.deserialize(header, frames)
