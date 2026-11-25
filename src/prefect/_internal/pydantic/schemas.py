from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic_core import core_schema


class GenerateEmptySchemaForUserClasses(GenerateJsonSchema):
    """
    This custom schema overrides the default pydantic is-instance schema
    behavior to simply return an empty dict for user-defined classes, and
    adds the member names of `Enum` types as `x-enum-varnames` so they can be
    displayed alongside their values
    """

    def is_instance_schema(
        self, schema: core_schema.IsInstanceSchema
    ) -> JsonSchemaValue:
        return {}

    def enum_schema(self, schema: core_schema.EnumSchema) -> JsonSchemaValue:
        result = super().enum_schema(schema)
        result["x-enum-varnames"] = [member.name for member in schema["members"]]
        return result
