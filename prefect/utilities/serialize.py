import base64
from collections import namedtuple
import distributed
from mongoengine import EmbeddedDocument
from mongoengine.fields import (DictField, ListField, StringField)
import prefect


class Serialized(EmbeddedDocument):
    type = StringField()
    header = DictField()
    frames = ListField(StringField(), required=True)
    meta = {'allow_inheritance': True}


def serialize(obj):
    """
    Serialize a Python object
    """
    header, frames = distributed.protocol.serialize(obj)
    frames = [base64.b64encode(b).decode('utf-8') for b in frames]
    return Serialized(header=header, frames=frames, type=type(obj).__name__)


def deserialize(serialized_obj):
    """
    Deserialize a Python object
    """
    header, frames = serialized_obj['header'], serialized_obj['frames']
    frames = [base64.b64decode(b.encode('utf-8')) for b in frames]
    return distributed.protocol.deserialize(header, frames)
