"""
Functions within this module check for Pydantic V2 compatibility and provide mechanisms for copying,
 dumping, and validating models in a way that is agnostic to the underlying Pydantic version.
"""

import typing

from ._base_model import BaseModel as PydanticBaseModel
from ._base_model import (
    ConfigDict,
    Field,
    FieldInfo,
    PrivateAttr,
    SecretStr,
    ValidationError,
)
from ._flags import HAS_PYDANTIC_V2, USE_PYDANTIC_V2
from .utilities.config_dict import ConfigMixin
from .utilities.field_validator import field_validator
from .utilities.model_construct import ModelConstructMixin, model_construct
from .utilities.model_copy import ModelCopyMixin, model_copy
from .utilities.model_dump import ModelDumpMixin, model_dump
from .utilities.model_dump_json import ModelDumpJsonMixin, model_dump_json
from .utilities.model_fields import ModelFieldMixin
from .utilities.model_fields_set import ModelFieldsSetMixin, model_fields_set
from .utilities.model_json_schema import ModelJsonSchemaMixin, model_json_schema
from .utilities.model_validate import ModelValidateMixin, model_validate
from .utilities.model_validate_json import ModelValidateJsonMixin, model_validate_json
from .utilities.model_validator import model_validator
from .utilities.type_adapter import TypeAdapter, validate_python

if typing.TYPE_CHECKING:

    class BaseModel(PydanticBaseModel):  # type: ignore
        pass

elif HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
    # In this case, there's no functionality to add, so we just alias the Pydantic v2 BaseModel
    class BaseModel(PydanticBaseModel):  # type: ignore
        pass

else:
    # In this case, we're working with a Pydantic v1 model, so we need to add Pydantic v2 functionality
    # TODO: Find a smarter way of attaching these methods so that they don't need to be redefined

    class BaseModel(
        ModelConstructMixin,
        ModelCopyMixin,
        ModelDumpMixin,
        ModelDumpJsonMixin,
        ModelJsonSchemaMixin,
        ModelValidateMixin,
        ModelValidateJsonMixin,
        ModelFieldMixin,
        ConfigMixin,
        ModelFieldsSetMixin,
        PydanticBaseModel,
    ):
        pass


__all__ = [
    "model_construct",
    "model_copy",
    "model_dump",
    "model_dump_json",
    "model_json_schema",
    "model_validate",
    "model_validate_json",
    "model_fields_set",
    "TypeAdapter",
    "validate_python",
    "BaseModel",
    "Field",
    "FieldInfo",
    "field_validator",
    "model_validator",
    "PrivateAttr",
    "SecretStr",
    "ConfigDict",
    "ValidationError",
]
