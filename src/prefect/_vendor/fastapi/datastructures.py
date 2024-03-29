from typing import Any, Callable, Dict, Iterable, Type, TypeVar

from prefect._vendor.starlette.datastructures import URL as URL  # noqa: F401
from prefect._vendor.starlette.datastructures import Address as Address  # noqa: F401
from prefect._vendor.starlette.datastructures import FormData as FormData  # noqa: F401
from prefect._vendor.starlette.datastructures import Headers as Headers  # noqa: F401
from prefect._vendor.starlette.datastructures import (
    QueryParams as QueryParams,  # noqa: F401
)
from prefect._vendor.starlette.datastructures import State as State  # noqa: F401
from prefect._vendor.starlette.datastructures import UploadFile as StarletteUploadFile


class UploadFile(StarletteUploadFile):
    @classmethod
    def __get_validators__(cls: Type["UploadFile"]) -> Iterable[Callable[..., Any]]:
        yield cls.validate

    @classmethod
    def validate(cls: Type["UploadFile"], v: Any) -> Any:
        if not isinstance(v, StarletteUploadFile):
            raise ValueError(f"Expected UploadFile, received: {type(v)}")
        return v

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        field_schema.update({"type": "string", "format": "binary"})


class DefaultPlaceholder:
    """
    You shouldn't use this class directly.

    It's used internally to recognize when a default value has been overwritten, even
    if the overridden default value was truthy.
    """

    def __init__(self, value: Any):
        self.value = value

    def __bool__(self) -> bool:
        return bool(self.value)

    def __eq__(self, o: object) -> bool:
        return isinstance(o, DefaultPlaceholder) and o.value == self.value


DefaultType = TypeVar("DefaultType")


def Default(value: DefaultType) -> DefaultType:
    """
    You shouldn't use this function directly.

    It's used internally to recognize when a default value has been overwritten, even
    if the overridden default value was truthy.
    """
    return DefaultPlaceholder(value)  # type: ignore
