# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from typing import Any

from prefect import Task
from prefect.serializers import Serializer


class SerializeTask(Task):
    """
    Serialize a result using a serializer. The serialized result must be less than 1kb.

    Args:
        - serializer (prefect.serializers.Seralizer): serializer to use
        - *args: additional args to pass to `Task` initialization
        - *kwargs: additional kwargs to pass to `Task` initialization
    """

    def __init__(self, serializer: Serializer, *args: Any, **kwargs: Any) -> None:
        self.serializer = serializer
        super().__init__(*args, **kwargs)

    def run(self, data: Any) -> str:  # type: ignore
        """
        Serializes provided data using `self.serialize`

        Args:
            - data (Any): data to serialize

        Returns:
            - str: serialized data
        """
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

    Args:
        - serializer (prefect.serializers.Seralizer): serializer to use
        - *args: additional args to pass to `Task` initialization
        - *kwargs: additional kwargs to pass to `Task` initialization
    """

    def __init__(self, serializer: Serializer, *args: Any, **kwargs: Any) -> None:
        self.serializer = serializer
        super().__init__(*args, **kwargs)

    def run(self, serialized: str) -> Any:  # type: ignore
        """
        Deserializes provided data using `self.serialize`

        Args:
            - data (str): data to serialize

        Returns:
            - deserialized data
        """
        return self.serializer.deserialize(serialized)
