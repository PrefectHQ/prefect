# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

from typing import Any, Union

from prefect.engine.result_serializers import ResultSerializer


ResultType = Union["Result", "NoResult"]


class Result:
    def __init__(
        self, value: Any, serialized: bool = False, serializer: ResultSerializer = None
    ):
        self.value = value
        if serialized is True and serializer is None:
            raise ValueError("If value is serialized, a serializer must be provided.")

        self.serialized = serialized
        self.serializer = serializer

    def serialize(self) -> "Result":
        value = self.value
        if not self.serialized:
            value = self.serializer.serialize(self.value)
        return Result(value=value, serialized=True, serializer=self.serializer)

    def deserialize(self) -> "Result":
        value = self.value
        if self.serialized:
            value = self.serializer.deserialize(self.value)
        return Result(value=value, serialized=False, serializer=self.serializer)


class NoResult:
    def __init__(self):
        pass
