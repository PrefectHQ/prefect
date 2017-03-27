import base64
from collections import namedtuple
import distributed
from mongoengine import EmbeddedDocument
from mongoengine.fields import (DictField, ListField, StringField)
import prefect


class Serialized(EmbeddedDocument):
    type = StringField()
    header = DictField(required=True)
    frames = ListField(StringField(), required=True)

    meta = {'allow_inheritance': True}


class SerializedFlow(Serialized):

    def __init__(self, header, frames, type):
        if not isinstance(type, prefect.flow.Flow):
            raise TypeError('Expected a Flow, received {}'.format(type))
        super().__init__(header=header, frames=frames, type=type)


class SerializedTask(Serialized):

    def __init__(self, header, frames, type):
        if not isinstance(type, prefect.task.Task):
            raise TypeError('Expected a Task, received {}'.format(type))
        super().__init__(header=header, frames=frames, type=type)


def serialize(obj):
    """
    Serialize a Python object
    """
    header, frames = distributed.protocol.serialize(obj)
    frames = [base64.b64encode(b).decode('utf-8') for b in frames]
    if isinstance(obj, prefect.flow.Flow):
        return SerializedFlow(
            header=header, frames=frames, type=type(obj).__name__)
    elif isinstance(obj, prefect.task.Task):
        return SerializedTask(
            header=header, frames=frames, type=type(obj).__name__)
    else:
        return Serialized(header=header, frames=frames, type=type(obj).__name__)


def deserialize(serialized_obj):
    """
    Deserialize a Python object
    """
    header, frames = serialized_obj['header'], serialized_obj['frames']
    frames = [base64.b64decode(b.encode('utf-8')) for b in frames]
    return distributed.protocol.deserialize(header, frames)
