from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic_core import SchemaValidator, core_schema

T = TypeVar("T", bound=BaseModel)

ListValidator: SchemaValidator = SchemaValidator(
    schema=core_schema.list_schema(
        items_schema=core_schema.dict_schema(
            keys_schema=core_schema.str_schema(), values_schema=core_schema.any_schema()
        )
    )
)


def validate_list(model: type[T], input: Any) -> list[T]:
    return [model.model_validate(item) for item in ListValidator.validate_python(input)]
