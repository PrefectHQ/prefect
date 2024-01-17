from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic_core import core_schema


class GenerateEmptySchemaForUserClasses(GenerateJsonSchema):
    """
    This custom schema overrides the default pydantic is-instance schema
    behavior to simply return an empty dict for user-defined classes
    """

    def is_instance_schema(
        self, schema: core_schema.IsInstanceSchema
    ) -> JsonSchemaValue:
        return {}
