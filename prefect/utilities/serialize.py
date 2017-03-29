import base64
from collections import namedtuple
import distributed
from mongoengine import EmbeddedDocument, fields
import prefect



class Serialized(EmbeddedDocument):
    type = fields.StringField()
    header = fields.DictField()
    frames = fields.ListField(fields.StringField(), required=True)
    meta = {'allow_inheritance': True}


    @classmethod
    def serialize(cls, obj):
        """
        Serialize a Python object
        """
        header, frames = distributed.protocol.serialize(obj)
        frames = [base64.b64encode(b).decode('utf-8') for b in frames]
        return cls(header=header, frames=frames, type=type(obj).__name__)

    def deserialize(self):
        """
        Deserialize a Python object
        """
        header, frames = self['header'], self['frames']
        frames = [base64.b64decode(b.encode('utf-8')) for b in frames]
        return distributed.protocol.deserialize(header, frames)
