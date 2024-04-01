from ._base_model import BaseModel as PydanticBaseModel
from ._flags import HAS_PYDANTIC_V2, USE_PYDANTIC_V2
from .utilities.model_construct import ModelConstructMixin, model_construct
from .utilities.model_copy import ModelCopyMixin, model_copy
from .utilities.model_dump import ModelDumpMixin, model_dump
from .utilities.model_dump_json import ModelDumpJsonMixin, model_dump_json
from .utilities.model_json_schema import ModelJsonSchemaMixin, model_json_schema
from .utilities.model_validate import ModelValidateMixin, model_validate
from .utilities.model_validate_json import ModelValidateJsonMixin, model_validate_json
from .utilities.type_adapter import TypeAdapter, validate_python

if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
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
    "TypeAdapter",
    "validate_python",
    "BaseModel",
]
