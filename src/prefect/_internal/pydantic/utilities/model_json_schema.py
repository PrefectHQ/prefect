import typing

from prefect._internal.pydantic._flags import USE_V2_MODELS

if typing.TYPE_CHECKING:
    from prefect._internal.pydantic._base_model import BaseModel
    from prefect._internal.pydantic._types import JsonSchemaMode

from prefect._internal.pydantic._types import DEFAULT_REF_TEMPLATE

T = typing.TypeVar("T", bound="BaseModel")

if USE_V2_MODELS:

    def model_json_schema(
        model: typing.Type["BaseModel"],
        *,
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: typing.Any = None,
        mode: JsonSchemaMode = "validation",
    ) -> typing.Dict[str, typing.Any]:
        return model.model_json_schema(
            by_alias=by_alias,
            ref_template=ref_template,
            schema_generator=schema_generator,
            mode=mode,
        )

else:

    def model_json_schema(
        model: typing.Type["BaseModel"],
        *,
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: typing.Any = None,
        mode: "JsonSchemaMode" = "validation",
    ) -> typing.Dict[str, typing.Any]:
        return getattr(model, "schema")(
            by_alias=by_alias,
            ref_template=ref_template,
        )


__all__ = ["model_json_schema"]
