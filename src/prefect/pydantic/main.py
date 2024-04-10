"""
This file defines a `PrefectBaseModel` class that extends the `BaseModel` (imported from the internal compatibility layer).
"""
import typing

from prefect._internal.pydantic._compat import (
    BaseModel,
    ConfigDict,
    Field,
    FieldInfo,
    PrivateAttr,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)


class PrefectBaseModel(BaseModel):
    def _reset_fields(self) -> typing.Set[str]:
        """
        A set of field names that are reset when the PrefectBaseModel is copied.
        These fields are also disregarded for equality comparisons.
        """
        return set()


__all__ = [
    "BaseModel",
    "PrefectBaseModel",
    "Field",
    "FieldInfo",
    "PrivateAttr",
    "SecretStr",
    "field_validator",
    "model_validator",
    "ConfigDict",
    "ValidationError",
]
