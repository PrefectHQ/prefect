from typing import Any, Callable, ClassVar, Generator

from pydantic_core import core_schema, CoreSchema, SchemaValidator
from typing_extensions import Self
from datetime import timedelta


class NonNegativeInteger(int):
    """An integer that must be greater than or equal to 0."""

    schema: ClassVar[CoreSchema] = core_schema.int_schema(ge=0)

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
        return SchemaValidator(schema=cls.schema).validate_python(v)


class PositiveInteger(int):
    """An integer that must be greater than 0."""

    schema: ClassVar[CoreSchema] = core_schema.int_schema(gt=0)

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
        return SchemaValidator(schema=cls.schema).validate_python(v)


class NonNegativeFloat(float):
    schema: ClassVar[CoreSchema] = core_schema.float_schema(ge=0)

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
        return SchemaValidator(schema=cls.schema).validate_python(v)


class NonNegativeDuration(timedelta):
    """A timedelta that must be greater than or equal to 0."""

    schema: ClassVar = core_schema.timedelta_schema(ge=timedelta(seconds=0))

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
        return SchemaValidator(schema=cls.schema).validate_python(v)


class PositiveDuration(timedelta):
    """A timedelta that must be greater than 0."""

    schema: ClassVar = core_schema.timedelta_schema(gt=timedelta(seconds=0))

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
        return SchemaValidator(schema=cls.schema).validate_python(v)


__all__ = [
    "NonNegativeInteger",
    "PositiveInteger",
    "NonNegativeFloat",
    "NonNegativeDuration",
    "PositiveDuration",
]
