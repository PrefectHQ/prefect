from typing import Any

from prefect import Task
from prefect.serializers import Serializer


class SerializeTask(Task):
    """
    Serialize a result using a serializer. The serialized result must be less than 1kb.
    """

    def __init__(self, serializer: Serializer, *args, **kwargs) -> None:
        self.serializer = serializer
        super().__init__(*args, **kwargs)

    def run(self, data: Any) -> str:
        serialized = self.serializer.serialize(data)
        if not isinstance(serialized, str):
            raise TypeError(
                "Serialized value must be a string; received {}".format(
                    type(serialized)
                )
            )
        elif len(serialized.encode("utf-8")) > 1024:
            raise ValueError("Serialized values must be less than 1kb")
        return serialized


class DeserializeTask(Task):
    """
    Deserialize a result from a serialized value.
    """

    def __init__(self, serializer: Serializer, *args, **kwargs) -> None:
        self.serializer = serializer
        super().__init__(*args, **kwargs)

    def run(self, serialized: str) -> Any:
        return self.serializer.deserialize(serialized)
