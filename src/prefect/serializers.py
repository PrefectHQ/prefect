import json
from typing import Any


class Serializer:
    @classmethod
    def serialize(cls, object: Any) -> str:
        raise NotImplementedError()

    @classmethod
    def deserialize(cls, key: str) -> Any:
        raise NotImplementedError()

class JSONSerializer:
    @classmethod
    def serialize(cls, object: Any) -> str:
        return json.dumps(object)

    @classmethod
    def deserialize(cls, key: str) -> Any:
        return json.loads(key)
