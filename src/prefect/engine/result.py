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
        if not self.serialized:
            assert isinstance(
                self.serializer, ResultSerializer
            ), "Result has no ResultSerializer"
            value = self.serializer.serialize(self.value)
            return Result(value=value, serialized=True, serializer=self.serializer)
        else:
            return self

    def deserialize(self) -> "Result":
        if self.serialized:
            assert isinstance(
                self.serializer, ResultSerializer
            ), "Result has no ResultSerializer"
            value = self.serializer.deserialize(self.value)
            return Result(value=value, serialized=False, serializer=self.serializer)
        else:
            return self


class NoResult:
    def __init__(self) -> None:
        pass
