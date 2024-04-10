### A convenience module to allow for easy switching between pydantic versions.

### Note this introduces a marginally worse import time, since
### the import of any one of these symbols will import all of them.

### This is a tradeoff we're willing to make for now until pydantic v1 is
### no longer supported.


from ._flags import HAS_PYDANTIC_V2

from ._compat import (
    model_dump,
    model_json_schema,
    model_validate,
    model_dump_json,
    model_copy,
    model_validate_json,
    TypeAdapter,
    validate_python,
    BaseModel,
    Field,
    FieldInfo,
    field_validator,
    model_validator,
)

from ._types import IncEx

__all__ = [
    "model_dump",
    "model_json_schema",
    "model_validate",
    "IncEx",
    "model_dump_json",
    "model_copy",
    "model_validate_json",
    "TypeAdapter",
    "validate_python",
    "BaseModel",
    "HAS_PYDANTIC_V2",
    "Field",
    "FieldInfo",
    "field_validator",
    "model_validator",
]
