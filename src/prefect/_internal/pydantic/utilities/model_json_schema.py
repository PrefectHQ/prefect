import typing

from typing_extensions import Self

from prefect._internal.pydantic._base_model import BaseModel
from prefect._internal.pydantic._flags import USE_V2_MODELS

if typing.TYPE_CHECKING:
    from prefect._internal.pydantic._types import JsonSchemaMode

from prefect._internal.pydantic._types import DEFAULT_REF_TEMPLATE

T = typing.TypeVar("T", bound="BaseModel")


def model_json_schema(
    model: typing.Type["BaseModel"],
    by_alias: bool = True,
    ref_template: str = DEFAULT_REF_TEMPLATE,
    schema_generator: typing.Any = None,
    mode: "JsonSchemaMode" = "validation",
) -> typing.Dict[str, typing.Any]:
    """
    Generates a JSON schema for a model class.

    Args:
        by_alias: Whether to use attribute aliases or not.
        ref_template: The reference template.
        schema_generator: To override the logic used to generate the JSON schema, as a subclass of
            `GenerateJsonSchema` with your desired modifications
        mode: The mode in which to generate the schema.

    Returns:
        The JSON schema for the given model class.
    """
    if USE_V2_MODELS:
        return model.model_json_schema(
            by_alias=by_alias,
            ref_template=ref_template,
            schema_generator=schema_generator,
            mode=mode,
        )
    else:
        return getattr(model, "schema")(
            by_alias=by_alias,
            ref_template=ref_template,
        )


class ModelJsonSchemaMixin(BaseModel):
    @classmethod
    def model_json_schema(
        cls: typing.Type["Self"],
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: typing.Any = None,
        mode: "JsonSchemaMode" = "validation",
    ) -> typing.Dict[str, typing.Any]:
        """
        Generates a JSON schema for a model class.

        Args:
            by_alias: Whether to use attribute aliases or not.
            ref_template: The reference template.
            schema_generator: To override the logic used to generate the JSON schema, as a subclass of
                `GenerateJsonSchema` with your desired modifications
            mode: The mode in which to generate the schema.

        Returns:
            The JSON schema for the given model class.
        """
        return model_json_schema(
            cls,
            by_alias=by_alias,
            ref_template=ref_template,
            schema_generator=schema_generator,
            mode=mode,
        )


__all__ = ["model_json_schema", "ModelJsonSchemaMixin"]
