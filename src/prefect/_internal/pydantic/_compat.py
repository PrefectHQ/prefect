from typing import Any, Dict, Literal, Optional, Set, Type, Union

import typing_extensions
from pydantic import BaseModel

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect._internal.pydantic.schemas import GenerateEmptySchemaForUserClasses
from prefect.logging.loggers import get_logger
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS

IncEx: typing_extensions.TypeAlias = (
    "Union[Set[int], Set[str], Dict[int, Any], Dict[str, Any], None]"
)

logger = get_logger("prefect._internal.pydantic")


def is_pydantic_v2_compatible(
    _model_instance: Optional[BaseModel] = None, fn_name: Optional[str] = None
) -> bool:
    if not isinstance(_model_instance, BaseModel):
        raise TypeError(
            f"Expected a Pydantic model, but got {type(_model_instance).__name__}"
        )

    should_dump_as_v2_model = (
        HAS_PYDANTIC_V2 and PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS
    )

    if should_dump_as_v2_model:
        logger.debug(
            f"Using Pydantic v2 compatibility layer for `{fn_name}`. This will be removed in a future release."
        )

        return True

    elif HAS_PYDANTIC_V2:
        logger.debug(
            "Pydantic v2 compatibility layer is disabled. To enable, set `PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS` to `True`."
        )

    else:
        logger.debug("Pydantic v2 is not installed.")

    return False


def model_dump(
    model_instance: BaseModel,
    *,
    mode: Union[Literal["json", "python"], str] = "python",
    include: IncEx = None,
    exclude: IncEx = None,
    by_alias: bool = False,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
    round_trip: bool = False,
    warnings: bool = True,
) -> Dict[str, Any]:
    if is_pydantic_v2_compatible(_model_instance=model_instance, fn_name="model_dump"):
        return model_instance.model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
        )

    return model_instance.dict(
        include=include,
        exclude=exclude,
        by_alias=by_alias,
        exclude_unset=exclude_unset,
        exclude_defaults=exclude_defaults,
        exclude_none=exclude_none,
    )


DEFAULT_REF_TEMPLATE = "#/$defs/{model}"

JsonSchemaMode = Literal["validation", "serialization"]


def model_json_schema(
    model_instance: BaseModel,
    *,
    by_alias: bool = True,
    # ref_template: str = DEFAULT_REF_TEMPLATE,
    schema_generator: Type[
        GenerateEmptySchemaForUserClasses
    ] = GenerateEmptySchemaForUserClasses,
    mode: JsonSchemaMode = "validation",
):
    """
    Generates a JSON schema for a model class.

    Parameters
    ----------
    by_alias : bool, optional
        Whether to use attribute aliases or not, by default True
    ref_template : str, optional
        The reference template, by default DEFAULT_REF_TEMPLATE
    schema_generator : type[GenerateEmptySchemaForUserClasses], optional
        To override the logic used to generate the JSON schema, as a subclass of GenerateEmptySchemaForUserClasses with your desired modifications, by default GenerateEmptySchemaForUserClasses
    mode : JsonSchemaMode, optional
        The mode in which to generate the schema, by default 'validation'

    Returns
    -------
    dict[str, Any]
        The JSON schema for the given model class.
    """
    pass
    # if is_pydantic_v2_compatible(
    #     _model_instance=model_instance, fn_name="model_json_schema"
    # ):
    #     return model_instance.model_json_schema(
    #         by_alias=by_alias,
    #         # ref_template=ref_template,
    #         schema_generator=schema_generator,
    #         mode=mode,
    #     )

    # return model_instance.schema(
    #     by_alias=by_alias,
    #     # ref_template=ref_template,
    # )
