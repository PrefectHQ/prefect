# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula
from typing import Callable
import sys
import marshmallow
import json


class JSONField(marshmallow.fields.Field):
    def __init__(
        self, max_size: int = None, dump_fn: Callable = None, **kwargs
    ) -> None:
        """
        Args:
            - max_size (int): the maximum size of the payload, in bytes
            - dump_fn (callable): a function of (obj, context) that should return a JSON-able
                payload during serialization
        """
        super().__init__(**kwargs)
        self.max_size = max_size
        self.dump_fn = dump_fn

        if dump_fn is not None:
            self._CHECK_ATTRIBUTE = False

    def _serialize(self, value, attr, obj, **kwargs):
        if self.dump_fn is not None:
            value = self.dump_fn(obj, self.context)
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


class NestedField(marshmallow.fields.Nested):
    """
    An extension of the Marshmallow Nested field that allows the value to be selected
    via a dump_fn.
    """

    def __init__(self, nested: type, dump_fn: Callable = None, **kwargs) -> None:
        super().__init__(nested=nested, **kwargs)
        self.dump_fn = dump_fn

        if dump_fn is not None:
            self._CHECK_ATTRIBUTE = False

    def _serialize(self, value, attr, obj, **kwargs):
        if self.dump_fn is not None:
            value = self.dump_fn(obj, self.context)
        return super()._serialize(value, attr, obj, **kwargs)
