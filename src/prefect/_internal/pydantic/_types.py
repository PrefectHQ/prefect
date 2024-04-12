from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Dict, Literal, Set, Union

from pydantic_core import CoreSchema, SchemaValidator, core_schema
from typing_extensions import Self, TypeAlias

IncEx: TypeAlias = "Union[Set[int], Set[str], Dict[int, Any], Dict[str, Any], None]"

DEFAULT_REF_TEMPLATE = "#/$defs/{model}"
JsonSchemaMode = Literal["validation", "serialization"]


@dataclass
class NonNegativeInteger(int):
    schema: ClassVar[CoreSchema] = core_schema.int_schema(ge=0)

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Callable[..., Any]
    ) -> CoreSchema:
        return cls.schema

    @classmethod
    def validate(cls, v) -> Self:
        return SchemaValidator(schema=cls.schema).validate_python(v)


@dataclass
class PositiveInteger(int):
    schema: ClassVar[CoreSchema] = core_schema.int_schema(gt=0)

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Callable[..., Any]
    ) -> CoreSchema:
        return cls.schema

    @classmethod
    def validate(cls, v) -> Self:
        return SchemaValidator(schema=cls.schema).validate_python(v)
