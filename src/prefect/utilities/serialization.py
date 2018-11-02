# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula
import sys
import marshmallow
import json


class JSONField(marshmallow.fields.Field):
    def __init__(self, max_size=None, **kwargs):
        super().__init__(**kwargs)
        self.max_size = max_size

    def _serialize(self, value, attr, obj, **kwargs):
        serialized = json.dumps(value)
        if self.max_size and sys.getsizeof(serialized) > self.max_size:
            raise ValueError(
                "Serialization payload exceeds max size of {} bytes.".format(
                    self.max_size
                )
            )
        return serialized

    def _deserialize(self, value, attr, data, **kwargs):
        if self.max_size and sys.getsizeof(value) > self.max_size:
            raise ValueError(
                "Deserialization payload exceeds max size of {} bytes.".format(
                    self.max_size
                )
            )
        return json.loads(value)
