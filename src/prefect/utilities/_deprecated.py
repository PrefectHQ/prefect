from typing import Any

from jsonpatch import (  # type: ignore  # no typing stubs available, see https://github.com/stefankoegl/python-json-patch/issues/158
    JsonPatch as JsonPatchBase,
)
from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema


class JsonPatch(JsonPatchBase):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetJsonSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.typed_dict_schema(
            {"patch": core_schema.typed_dict_field(core_schema.dict_schema())}
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema = handler.resolve_ref_schema(json_schema)
        json_schema.pop("required", None)
        json_schema.pop("properties", None)
        json_schema.update(
            {
                "type": "array",
                "format": "rfc6902",
                "items": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
            }
        )
        return json_schema
