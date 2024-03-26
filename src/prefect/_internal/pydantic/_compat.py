from typing import Any, Dict, Literal, Optional, Set, Type, TypeVar, Union

from typing_extensions import Self, TypeAlias

from prefect._internal.pydantic._flags import (
    HAS_PYDANTIC_V2,
    USE_PYDANTIC_V2,
)
from prefect.logging.loggers import get_logger

from ._base_model import BaseModel as PydanticBaseModel

IncEx: TypeAlias = "Union[Set[int], Set[str], Dict[int, Any], Dict[str, Any], None]"
logger = get_logger("prefect._internal.pydantic")

if HAS_PYDANTIC_V2:
    from pydantic.json_schema import GenerateJsonSchema  # type: ignore

T = TypeVar("T", bound=PydanticBaseModel)


def is_pydantic_v2_compatible(
    model_instance: PydanticBaseModel, fn_name: Optional[str] = None
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
    model_instance : Optional[PydanticBaseModel], optional
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
        If `model_instance` is provided but is not an instance of a Pydantic PydanticBaseModel.
    """

    if model_instance and not isinstance(model_instance, PydanticBaseModel):  # type: ignore
        raise TypeError(
            f"Expected a Pydantic model, but got {type(model_instance).__name__}"
        )

    if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
        logger.debug(
            f"Using Pydantic v2 compatibility layer for `{fn_name}`. This will be removed in a future release."
        )

        return True

    elif HAS_PYDANTIC_V2 and not USE_PYDANTIC_V2:
        logger.debug(
            "Pydantic v2 compatibility layer is disabled. To enable, set `PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS` to `True`."
        )

    else:
        logger.debug("Pydantic v2 is not installed.")

    return False


def model_copy(
    model_instance: PydanticBaseModel,
    *,
    update: Optional[Dict[str, Any]] = None,
    deep: bool = False,
) -> PydanticBaseModel:
    """Usage docs: https://docs.pydantic.dev/2.7/concepts/serialization/#model_copy

    Returns a copy of the model.

    Args:
        update: Values to change/add in the new model. Note: the data is not validated
            before creating the new model. You should trust this data.
        deep: Set to `True` to make a deep copy of the model.

    Returns:
        New model instance.
    """
    if is_pydantic_v2_compatible(model_instance=model_instance, fn_name="model_copy"):
        return model_instance.model_copy(update=update, deep=deep)

    return model_instance.copy(update=update, deep=deep)  # type: ignore


def model_dump_json(
    model_instance: PydanticBaseModel,
    *,
    indent: Optional[int] = None,
    include: IncEx = None,
    exclude: IncEx = None,
    by_alias: bool = False,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
    round_trip: bool = False,
    warnings: bool = True,
) -> str:
    """
    Generate a JSON representation of the model, optionally specifying which fields to include or exclude.

    Args:
        indent: If provided, the number of spaces to indent the JSON output.
        include: A list of fields to include in the output.
        exclude: A list of fields to exclude from the output.
        by_alias: Whether to use the field's alias in the dictionary key if defined.
        exclude_unset: Whether to exclude fields that have not been explicitly set.
        exclude_defaults: Whether to exclude fields that are set to their default value.
        exclude_none: Whether to exclude fields that have a value of `None`.
        round_trip: If True, dumped values should be valid as input for non-idempotent types such as Json[T].
        warnings: Whether to log warnings when invalid fields are encountered.

    Returns:
        A JSON representation of the model.
    """
    if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
        return model_instance.model_dump_json(
            indent=indent,
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
        )

    return model_instance.json(  # type: ignore
        include=include,
        exclude=exclude,
        by_alias=by_alias,
        exclude_unset=exclude_unset,
        exclude_defaults=exclude_defaults,
        exclude_none=exclude_none,
    )


def model_dump(
    model_instance: PydanticBaseModel,
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
    if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
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

    return getattr(model_instance, "dict")(
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
    model: Type[PydanticBaseModel],
    *,
    by_alias: bool = True,
    ref_template: str = DEFAULT_REF_TEMPLATE,
    schema_generator: Any = None,
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
    if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
        schema_generator = GenerateJsonSchema  # type: ignore
        return model.model_json_schema(
            by_alias=by_alias,
            ref_template=ref_template,
            schema_generator=schema_generator,
            mode=mode,
        )

    return model.schema(  # type: ignore
        by_alias=by_alias,
        ref_template=ref_template,
    )


def model_validate(
    model: Type[T],
    obj: Any,
    *,
    strict: Optional[bool] = False,
    from_attributes: Optional[bool] = False,
    context: Optional[Dict[str, Any]] = None,
) -> T:
    """Validate a pydantic model instance.

    Args:
        obj: The object to validate.
        strict: Whether to enforce types strictly.
        from_attributes: Whether to extract data from object attributes.
        context: Additional context to pass to the validator.

    Raises:
        ValidationError: If the object could not be validated.

    Returns:
        The validated model instance.
    """
    if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
        return model.model_validate(
            obj=obj,
            strict=strict,
            from_attributes=from_attributes,
            context=context,
        )

    return getattr(model, "validate")(obj)


def model_validate_json(
    model: Type[T],
    json_data: Union[str, bytes, bytearray],
    *,
    strict: bool = False,
    context: Optional[Dict[str, Any]] = None,
) -> T:
    """Validate the given JSON data against the Pydantic model.

    Args:
        json_data: The JSON data to validate.
        strict: Whether to enforce types strictly.
        context: Extra variables to pass to the validator.

    Returns:
        The validated Pydantic model.

    Raises:
        ValueError: If `json_data` is not a JSON string.
    """
    if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
        return model.model_validate_json(
            json_data=json_data,
            strict=strict,
            context=context,
        )

    return getattr(model, "parse_raw")(json_data)


if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
    # In this case, there's no functionality to add, so we just alias the Pydantic v2 BaseModel
    class BaseModel(PydanticBaseModel):  # type: ignore
        pass

else:
    # In this case, we're working with a Pydantic v1 model, so we need to add Pydantic v2 functionality
    class BaseModel(PydanticBaseModel):
        def model_dump(
            self: "BaseModel",
            *,
            mode: str = "python",
            include: IncEx = None,
            exclude: IncEx = None,
            by_alias: bool = False,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = False,
            round_trip: bool = False,
            warnings: bool = True,
        ) -> Dict[str, Any]:
            return model_dump(
                self,
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

        def model_dump_json(
            self,
            *,
            indent: Optional[int] = None,
            include: Optional[IncEx] = None,
            exclude: Optional[IncEx] = None,
            by_alias: bool = False,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = False,
            round_trip: bool = False,
            warnings: bool = True,
        ) -> str:
            return super().model_dump_json(
                indent=indent,
                include=include,
                exclude=exclude,
                by_alias=by_alias,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
                round_trip=round_trip,
                warnings=warnings,
            )

        def model_copy(
            self: "Self",
            *,
            update: Optional[Dict[str, Any]] = None,
            deep: bool = False,
        ) -> "Self":
            return super().model_copy(update=update, deep=deep)

        @classmethod
        def model_json_schema(
            cls,
            by_alias: bool = True,
            ref_template: str = DEFAULT_REF_TEMPLATE,
            schema_generator: Any = None,
            mode: JsonSchemaMode = "validation",
        ) -> Dict[str, Any]:
            return model_json_schema(
                cls,
                by_alias=by_alias,
                ref_template=ref_template,
                schema_generator=schema_generator,
                mode=mode,
            )

        @classmethod
        def model_validate(
            cls: Type["Self"],
            obj: Any,
            *,
            strict: Optional[bool] = False,
            from_attributes: Optional[bool] = False,
            context: Optional[Dict[str, Any]] = None,
        ) -> "Self":
            return model_validate(
                cls,
                obj,
                strict=strict,
                from_attributes=from_attributes,
                context=context,
            )
