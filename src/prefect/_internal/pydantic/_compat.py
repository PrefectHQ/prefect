from typing import Any, Dict, Literal, Optional, Set, Type, Union

import typing_extensions
from pydantic import BaseModel

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.logging.loggers import get_logger
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS

IncEx: typing_extensions.TypeAlias = (
    "Union[Set[int], Set[str], Dict[int, Any], Dict[str, Any], None]"
)

logger = get_logger("prefect._internal.pydantic")

if HAS_PYDANTIC_V2:
    from pydantic.json_schema import GenerateJsonSchema


def is_pydantic_v2_compatible(
    model_instance: Optional[BaseModel] = None, fn_name: Optional[str] = None
) -> bool:
    """
    Determines if the current environment is compatible with Pydantic V2 features,
    based on the presence of Pydantic V2 and a global setting that enables V2 functionalities.

    This function primarily serves to facilitate conditional logic in code that needs to
    operate differently depending on the availability of Pydantic V2 features. It checks
    two conditions: whether Pydantic V2 is installed, and whether the use of V2 features
    is explicitly enabled through a global setting (`PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS`).

    Parameters:
    -----------
    model_instance : Optional[BaseModel], optional
        An instance of a Pydantic model. This parameter is used to perform a type check
        to ensure the passed object is a Pydantic model instance. If not provided or if
        the object is not a Pydantic model, a TypeError is raised. Defaults to None.

    fn_name : Optional[str], optional
        The name of the function or feature for which V2 compatibility is being checked.
        This is used for logging purposes to provide more context in debug messages.
        Defaults to None.

    Returns:
    --------
    bool
        True if the current environment supports Pydantic V2 features and if the global
        setting for enabling V2 features is set to True. False otherwise.

    Raises:
    -------
    TypeError
        If `model_instance` is provided but is not an instance of a Pydantic BaseModel.
    """
    if model_instance and not isinstance(model_instance, BaseModel):
        raise TypeError(
            f"Expected a Pydantic model, but got {type(model_instance).__name__}"
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
    """
    Generate a dictionary representation of the model, optionally specifying which fields to include or exclude.

    Args:
        mode: The mode in which `to_python` should run.
            If mode is 'json', the output will only contain JSON serializable types.
            If mode is 'python', the output may contain non-JSON-serializable Python objects.
        include: A list of fields to include in the output.
        exclude: A list of fields to exclude from the output.
        by_alias: Whether to use the field's alias in the dictionary key if defined.
        exclude_unset: Whether to exclude fields that have not been explicitly set.
        exclude_defaults: Whether to exclude fields that are set to their default value.
        exclude_none: Whether to exclude fields that have a value of `None`.
        round_trip: If True, dumped values should be valid as input for non-idempotent types such as Json[T].
        warnings: Whether to log warnings when invalid fields are encountered.

    Returns:
        A dictionary representation of the model.
    """
    if is_pydantic_v2_compatible(model_instance=model_instance, fn_name="model_dump"):
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
    model: Type[BaseModel],
    *,
    by_alias: bool = True,
    ref_template: str = DEFAULT_REF_TEMPLATE,
    schema_generator=None,
    mode: JsonSchemaMode = "validation",
) -> Dict[str, Any]:
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
    if is_pydantic_v2_compatible(fn_name="model_json_schema"):
        schema_generator = GenerateJsonSchema
        return model.model_json_schema(
            by_alias=by_alias,
            ref_template=ref_template,
            schema_generator=schema_generator,
            mode=mode,
        )

    return model.schema(
        by_alias=by_alias,
        ref_template=ref_template,
    )
