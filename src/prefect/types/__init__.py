from typing import Annotated, Any, Callable, ClassVar, Generator

from pydantic_core import core_schema, CoreSchema, SchemaValidator
from pydantic import Field
from typing_extensions import Self
from datetime import timedelta


NonNegativeInteger = Annotated[int, Field(ge=0)]


PositiveInteger = Annotated[int, Field(gt=0)]


NonNegativeFloat = Annotated[float, Field(ge=0.0)]


class NonNegativeDuration(timedelta):
    """A timedelta that must be greater than or equal to 0."""

    schema: ClassVar = core_schema.timedelta_schema(ge=timedelta(seconds=0))

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Callable[..., Any]
    ) -> CoreSchema:
        return cls.schema


class PositiveDuration(timedelta):
    """A timedelta that must be greater than 0."""

    schema: ClassVar = core_schema.timedelta_schema(gt=timedelta(seconds=0))

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Callable[..., Any]
    ) -> CoreSchema:
        return cls.schema


BANNED_CHARACTERS = ["/", "%", "&", ">", "<"]
WITHOUT_BANNED_CHARACTERS = r"^[^" + "".join(BANNED_CHARACTERS) + "]+$"


class Name(str):
    """A string that does not include characters that are problematic for URLs, file
    paths, or other escaping contexts"""

    schema: ClassVar = core_schema.str_schema(pattern=WITHOUT_BANNED_CHARACTERS)

    @classmethod
    def __get_validators__(cls) -> Generator[Callable[..., Any], None, None]:
        yield cls.validate

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Callable[..., Any]
    ) -> CoreSchema:
        return cls.schema

    @classmethod
    def validate(cls, v: Any) -> Self:
        if isinstance(v, str) and v:
            if not v.strip("' \""):
                raise ValueError("name cannot be an empty string")
        return SchemaValidator(schema=cls.schema).validate_python(v)


class NonEmptyishName(Name):
    """A Name that also doesn't include trailing whitespace or embedded quoted empty
    strings"""

    @classmethod
    def validate(cls, v: Any) -> Self:
        if isinstance(v, str) and v:
            if not v.strip("' \""):
                raise ValueError("name cannot be an empty string")
        return super().validate(v)


WITHOUT_BANNED_CHARACTERS_EMPTY_OK = r"^[^" + "".join(BANNED_CHARACTERS) + "]*$"


class NameOrEmpty(Name):
    """A Name that may also be an empty string"""

    schema: ClassVar = core_schema.str_schema(
        pattern=WITHOUT_BANNED_CHARACTERS_EMPTY_OK
    )


__all__ = [
    "NonNegativeInteger",
    "PositiveInteger",
    "NonNegativeFloat",
    "NonNegativeDuration",
    "PositiveDuration",
    "Name",
]
